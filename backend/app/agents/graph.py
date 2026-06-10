import logging
from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.supervisor import supervisor_node
from app.agents.researcher import researcher_node
from app.agents.writer import writer_node
from app.agents.judge import judge_node

logger = logging.getLogger(__name__)

# 1. Initialize StateGraph
workflow = StateGraph(AgentState)

# 2. Add structural nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("writer", writer_node)
workflow.add_node("judge", judge_node)

# 3. Define Entrypoint
workflow.set_entry_point("supervisor")

# 4. Define conditional routing functions
def route_from_supervisor(state: AgentState) -> str:
    next_step = state.get("next_step")
    if next_step in ["researcher", "writer"]:
        return next_step
    return "end"

def route_from_judge(state: AgentState) -> str:
    next_step = state.get("next_step")
    if next_step == "writer":
        return "writer"
    return "end"

# 5. Add edges and conditional branches
workflow.add_conditional_edges(
    "supervisor",
    route_from_supervisor,
    {
        "researcher": "researcher",
        "writer": "writer",
        "end": END
    }
)

# Researcher always returns to supervisor to decide next action path
workflow.add_edge("researcher", "supervisor")

# Writer always sends draft output to QA Judge
workflow.add_edge("writer", "judge")

# Judge conditionally loops back to Writer or concludes graph execution
workflow.add_conditional_edges(
    "judge",
    route_from_judge,
    {
        "writer": "writer",
        "end": END
    }
)

# 6. Compile Graph
graph = workflow.compile()
logger.info("Multi-Agent LangGraph compiled successfully.")


def _load_user_memory_context(user_id: int) -> str | None:
    """
    Fetches all Memori-stored facts for the user and formats them as a
    concise USER PROFILE block ready for injection into agent prompts.

    Returns None if no memories are found or an error occurs.
    """
    try:
        from app.core.database import SessionLocal
        from app.services.memory_service import MemoryService

        db = SessionLocal()
        try:
            memories = MemoryService.get_user_memories(db, user_id)
        finally:
            db.close()

        if not memories:
            return None

        # Build a compact numbered list of facts (most recent first, cap at 30)
        facts = [m["content"] for m in memories[:30] if m.get("content")]
        if not facts:
            return None

        lines = ["### USER PROFILE (Long-Term Memory — from previous conversations):"]
        for i, fact in enumerate(facts, 1):
            lines.append(f"{i}. {fact}")
        lines.append(
            "\nIMPORTANT: Use these facts to personalise responses. "
            "When asked to fill in sender name, title, or company details, "
            "pull the values from this profile — do NOT ask the user again."
        )
        return "\n".join(lines)

    except Exception as e:
        logger.error("Failed to load user memory context for user %s: %s", user_id, e)
        return None


_langfuse_client_initialized = False

def _initialize_langfuse_client():
    global _langfuse_client_initialized
    if _langfuse_client_initialized:
        return
    from app.core.config import settings
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse
            logger.info("Initializing Langfuse client singleton...")
            Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST
            )
            _langfuse_client_initialized = True
            logger.info("Langfuse client singleton initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize Langfuse client: %s", e)

def _get_langfuse_callback():
    """
    Instantiates a Langfuse CallbackHandler if public and secret telemetry keys are configured.
    """
    from app.core.config import settings
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        try:
            _initialize_langfuse_client()
            from langfuse.langchain import CallbackHandler
            logger.info("Initializing Langfuse CallbackHandler for LangGraph workflow")
            return CallbackHandler()
        except Exception as e:
            logger.warning("Failed to initialize Langfuse callback handler: %s", e)
    return None


# Global set to hold strong references to running background tasks to prevent garbage collection
_background_tasks = set()


def run_agent_workflow(
    messages: list,
    user_id: int,
    chat_id: int,
    mode: str = "general"
) -> dict:
    """
    Invokes the multi-agent graph with initial states and returns the final execution state dictionary.
    Loads long-term memory facts for the user and injects them into the state so the Writer
    can personalise responses without asking the user to repeat themselves.
    """
    # Retrieve and format user memory facts from Memori storage
    user_memory_context = _load_user_memory_context(user_id)
    if user_memory_context:
        logger.info(
            "Loaded %d memory facts for user %s into agent state.",
            user_memory_context.count("\n") - 1,
            user_id,
        )
    else:
        logger.info("No memory facts found for user %s — proceeding without memory context.", user_id)

    initial_state = {
        "messages": messages,
        "user_id": user_id,
        "chat_id": chat_id,
        "mode": mode,
        "user_memory_context": user_memory_context,
        "next_step": "supervisor",
        "research_query": None,
        "research_findings": [],
        "draft": None,
        "feedback": None,
        "critic_loops": 0,
        "final_response": None
    }

    logger.info(f"Invoking multi-agent workflow for user {user_id} in mode: {mode}")
    config = {}
    cb = _get_langfuse_callback()
    if cb:
        config["callbacks"] = [cb]
        config["metadata"] = {
            "langfuse_user_id": str(user_id),
            "langfuse_session_id": str(chat_id)
        }
        
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        async def _run_ainvoke():
            return await graph.ainvoke(initial_state, config=config)
            
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
            
        if loop and loop.is_running():
            with ThreadPoolExecutor() as executor:
                final_state = executor.submit(lambda: asyncio.run(_run_ainvoke())).result()
        else:
            final_state = asyncio.run(_run_ainvoke())
        
        # Save new extracted facts locally in the background
        final_response = final_state.get("final_response")
        if final_response and not final_response.startswith("[System Error"):
            latest_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            from app.services.memory_service import MemoryService
            from app.agents.writer import async_openai_client
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    task = loop.create_task(
                        MemoryService.extract_and_save_memories_async(
                            user_id=user_id,
                            user_msg=latest_user_message,
                            assistant_msg=final_response,
                            client=async_openai_client
                        )
                    )
                    _background_tasks.add(task)
                    task.add_done_callback(_background_tasks.discard)
                else:
                    loop.run_until_complete(
                        MemoryService.extract_and_save_memories_async(
                            user_id=user_id,
                            user_msg=latest_user_message,
                            assistant_msg=final_response,
                            client=async_openai_client
                        )
                    )
            except Exception:
                try:
                    new_loop = asyncio.new_event_loop()
                    new_loop.run_until_complete(
                        MemoryService.extract_and_save_memories_async(
                            user_id=user_id,
                            user_msg=latest_user_message,
                            assistant_msg=final_response,
                            client=async_openai_client
                        )
                    )
                except Exception as e:
                    logger.error("Failed to run local fact extraction background loop: %s", e)

        return final_state
    except Exception as e:
        logger.error(f"Failed to execute agent graph: {e}")
        return {
            "final_response": "[System Error: The agent workflow encountered a critical exception during execution.]",
            "research_findings": []
        }


async def run_agent_workflow_async(
    messages: list,
    user_id: int,
    chat_id: int,
    mode: str = "general",
    event_queue = None
) -> dict:
    """
    Invokes the multi-agent graph asynchronously. Loads long-term memory facts for the user,
    and passes the event_queue in the config for nodes to stream intermediate execution state and tokens.
    """
    # Retrieve and format user memory facts from Memori storage
    # Note: run in executor to keep database I/O from blocking async loop
    import asyncio
    loop = asyncio.get_event_loop()
    user_memory_context = await loop.run_in_executor(None, _load_user_memory_context, user_id)
    
    if user_memory_context:
        logger.info(
            "Loaded %d memory facts for user %s into agent state.",
            user_memory_context.count("\n") - 1,
            user_id,
        )
    else:
        logger.info("No memory facts found for user %s — proceeding without memory context.", user_id)

    initial_state = {
        "messages": messages,
        "user_id": user_id,
        "chat_id": chat_id,
        "mode": mode,
        "user_memory_context": user_memory_context,
        "next_step": "supervisor",
        "research_query": None,
        "research_findings": [],
        "draft": None,
        "feedback": None,
        "critic_loops": 0,
        "final_response": None
    }

    logger.info(f"Invoking multi-agent workflow async for user {user_id} in mode: {mode}")
    config = {"configurable": {"event_queue": event_queue}}
    cb = _get_langfuse_callback()
    if cb:
        config["callbacks"] = [cb]
        config["metadata"] = {
            "langfuse_user_id": str(user_id),
            "langfuse_session_id": str(chat_id)
        }
    
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        
        # Save new extracted facts locally in the background
        final_response = final_state.get("final_response")
        if final_response and not final_response.startswith("[System Error"):
            latest_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            from app.services.memory_service import MemoryService
            from app.agents.writer import async_openai_client
            task = asyncio.create_task(
                MemoryService.extract_and_save_memories_async(
                    user_id=user_id,
                    user_msg=latest_user_message,
                    assistant_msg=final_response,
                    client=async_openai_client
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return final_state
    except Exception as e:
        logger.error(f"Failed to execute agent graph async: {e}")
        return {
            "final_response": "[System Error: The agent workflow encountered a critical exception during execution.]",
            "research_findings": []
        }


