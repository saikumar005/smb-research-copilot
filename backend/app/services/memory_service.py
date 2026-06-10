import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from memori import Memori
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Initialize Memori wrapper pointing to our local PostgreSQL sessionmaker
try:
    from app.core.config import settings
    mem = Memori(conn=SessionLocal)
    if settings.MEMORI_API_KEY:
        mem.config.api_key = settings.MEMORI_API_KEY
    logger.info("Memori Labs memory infrastructure initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize Memori: {e}")
    mem = None

def init_memori_db() -> None:
    """
    Triggers schema creation for Memori tables in PostgreSQL.
    """
    if mem:
        try:
            logger.info("Ensuring Memori storage schema is built...")
            mem.config.storage.build()
            logger.info("Memori storage schema verified/built.")
        except Exception as e:
            logger.error(f"Error building Memori database schema: {e}")

class MemoryService:
    @staticmethod
    def get_user_memories(db: Session, user_id: int) -> List[Dict[str, Any]]:
        """
        Retrieves all long-term facts extracted by Memori for a specific user.

        Memori stores facts in two linked tables:
          - memori_entity         : maps our user ID (external_id) → internal entity id
          - memori_entity_fact    : one row per extracted fact, keyed by entity_id (FK)

        We join them so that each row returned contains the fact content and its
        internal primary-key ID (used for deletion).
        """
        try:
            query = text("""
                SELECT
                    ef.id           AS id,
                    e.external_id   AS entity_id,
                    ef.content      AS content,
                    ef.date_created AS created_at
                FROM memori_entity_fact ef
                JOIN memori_entity e ON e.id = ef.entity_id
                WHERE e.external_id = :external_id
                ORDER BY ef.date_created DESC
            """)
            result = db.execute(query, {"external_id": str(user_id)})

            memories = []
            for row in result.mappings():
                row_dict = dict(row)
                memories.append({
                    "id": str(row_dict["id"]),
                    "entity_id": str(row_dict["entity_id"]),
                    "content": row_dict.get("content") or "",
                    "created_at": row_dict.get("created_at"),
                })
            return memories
        except Exception as e:
            logger.error(f"Failed to query memori_entity_fact from DB: {e}")
            return []

    @staticmethod
    def delete_user_memory(db: Session, memory_id: str, user_id: int) -> bool:
        """
        Deletes a specific fact from memori_entity_fact, scoped to the requesting user
        to prevent cross-user deletions.

        The DELETE uses a sub-select on memori_entity to enforce ownership by external_id.
        """
        try:
            val_id = int(memory_id)
        except ValueError:
            logger.error(f"Invalid memory_id format (expected integer): {memory_id}")
            return False

        try:
            query = text("""
                DELETE FROM memori_entity_fact
                WHERE id = :fact_id
                  AND entity_id = (
                      SELECT id FROM memori_entity WHERE external_id = :external_id
                  )
            """)
            result = db.execute(query, {"fact_id": val_id, "external_id": str(user_id)})
            db.commit()
            # rowcount == 0 means either fact doesn't exist or doesn't belong to the user
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete memori_entity_fact record {memory_id}: {e}")
            db.rollback()
            return False

    @staticmethod
    def register_client(openai_client: Any) -> Any:
        """
        Bypasses default Memori cloud client registration to execute all LLM completions
        completely locally/offline, avoiding rate-limiting 429 errors.
        """
        return openai_client

    @staticmethod
    async def extract_and_save_memories_async(user_id: int, user_msg: str, assistant_msg: str, client: Any) -> None:
        """
        Analyzes the latest conversation turn using the LLM to extract long-term user facts
        and writes them directly to local PostgreSQL tables (memori_entity and memori_entity_fact).
        """
        if not user_msg or not assistant_msg:
            return

        import json
        import uuid
        import hashlib
        import struct
        from datetime import datetime
        from app.core.database import SessionLocal

        system_prompt = (
            "You are a long-term memory extraction assistant.\n"
            "Analyze the following user message and assistant reply.\n"
            "Extract any permanent facts about the user (e.g. user's name, title, role, company name, "
            "preferences, guidelines, constraints, or outreach style preferences).\n"
            "Do NOT extract temporary conversational context (e.g. details of a specific email draft, "
            "temporary search requests, or greeting text).\n"
            "Respond ONLY with a JSON object containing a list of strings: {\"facts\": [\"fact 1\", \"fact 2\"]}. "
            "If no long-term facts are found, return an empty list: {\"facts\": []}."
        )

        user_content = f"User message: \"{user_msg}\"\nAssistant reply: \"{assistant_msg}\""

        try:
            response = await client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            res_content = response.choices[0].message.content
            data = json.loads(res_content)
            facts = data.get("facts", [])
            if not facts:
                return

            logger.info("Local Memory: Extracted %d new facts for user %s: %s", len(facts), user_id, facts)

            # Batch generate embeddings for all extracted facts
            embs = []
            if mem:
                try:
                    embs = mem.embed_texts(facts)
                except Exception as embedding_err:
                    logger.error("Failed to generate embeddings using Memori: %s", embedding_err)

            db = SessionLocal()
            try:
                # Get or create entity
                query_entity = text("SELECT id FROM memori_entity WHERE external_id = :external_id")
                entity = db.execute(query_entity, {"external_id": str(user_id)}).fetchone()
                if entity:
                    entity_id = entity[0]
                else:
                    entity_uuid = str(uuid.uuid4())
                    insert_entity = text(
                        "INSERT INTO memori_entity (uuid, external_id, date_created, date_updated) "
                        "VALUES (:uuid, :external_id, :now, :now) RETURNING id"
                    )
                    entity_id = db.execute(insert_entity, {
                        "uuid": entity_uuid,
                        "external_id": str(user_id),
                        "now": datetime.now()
                    }).scalar()
                    db.commit()

                # For each fact, check uniqueness (using SHA-256 hash) and insert if new
                for idx, fact in enumerate(facts):
                    fact = fact.strip()
                    if not fact:
                        continue
                    
                    if len(fact) > 500:
                        fact = fact[:500]

                    # Generate uniq SHA256 hash of the content to enforce uniqueness
                    fact_hash = hashlib.sha256(fact.encode("utf-8")).hexdigest()

                    # Check if this uniq hash already exists for this entity
                    query_fact = text(
                        "SELECT id FROM memori_entity_fact "
                        "WHERE entity_id = :entity_id AND uniq = :uniq"
                    )
                    exists = db.execute(query_fact, {"entity_id": entity_id, "uniq": fact_hash}).fetchone()
                    if exists:
                        # Update date_last_time and increment num_times
                        update_fact = text(
                            "UPDATE memori_entity_fact "
                            "SET num_times = num_times + 1, date_last_time = :now, date_updated = :now "
                            "WHERE id = :id"
                        )
                        db.execute(update_fact, {"id": exists[0], "now": datetime.now()})
                    else:
                        # Serialize embedding as float32 bytes for PostgreSQL bytea
                        packed_emb = None
                        if idx < len(embs):
                            emb = embs[idx]
                            packed_emb = struct.pack(f"{len(emb)}f", *emb)
                        
                        if not packed_emb:
                            logger.warning("Skipping fact '%s' insertion because no embedding was generated.", fact)
                            continue

                        # Insert new fact
                        fact_uuid = str(uuid.uuid4())
                        insert_fact = text(
                            "INSERT INTO memori_entity_fact "
                            "(uuid, entity_id, content, content_embedding, num_times, date_last_time, uniq, date_created, date_updated) "
                            "VALUES (:uuid, :entity_id, :content, :content_embedding, 1, :now, :uniq, :now, :now)"
                        )
                        db.execute(insert_fact, {
                            "uuid": fact_uuid,
                            "entity_id": entity_id,
                            "content": fact,
                            "content_embedding": packed_emb,
                            "uniq": fact_hash,
                            "now": datetime.now()
                        })
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("Failed to write extracted facts to database: %s", e)
            finally:
                db.close()

        except Exception as e:
            logger.error("Failed local memory extraction: %s", e)
