import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from memori import Memori
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# Initialize Memori wrapper pointing to our local PostgreSQL sessionmaker
try:
    mem = Memori(conn=SessionLocal)
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
        Registers the OpenAI client with Memori to enable transparent fact extraction.
        Every LLM response routed through this registered client is automatically
        scanned; extracted facts are written to memori_entity_fact in PostgreSQL.
        """
        if mem:
            try:
                logger.info("Registering OpenAI client with Memori")
                return mem.llm.register(openai_client)
            except Exception as e:
                logger.error(f"Failed to register client with Memori: {e}")
        return openai_client
