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
    try:
        final_state = graph.invoke(initial_state)
        return final_state
    except Exception as e:
        logger.error(f"Failed to execute agent graph: {e}")
        return {
            "final_response": "[System Error: The agent workflow encountered a critical exception during execution.]",
            "research_findings": []
        }
