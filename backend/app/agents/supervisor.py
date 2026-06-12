import json
import logging
from openai import OpenAI, AsyncOpenAI
from app.core.config import settings
from app.services.memory_service import MemoryService
from app.agents.state import AgentState
from app.services.prompt_service import PromptService
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

# Initialize Gemini client unconditionally (using GEMINI_API_KEY or falling back to OPENAI_API_KEY)
api_key = settings.GEMINI_API_KEY
if not api_key or api_key.startswith("your-"):
    api_key = settings.OPENAI_API_KEY

if not api_key:
    api_key = "dummy-api-key"

openai_client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
async_openai_client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
MODEL_FAST = "gemini-2.5-flash"
MODEL_SMART = "gemini-2.5-pro"
logger.info("Supervisor Agent initialized using Gemini Client.")

mem_client = MemoryService.register_client(openai_client)

async def supervisor_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """
    Supervisor Agent analyzes user input and state to determine the routing path:
    - If live info is needed or mode is 'research', routes to 'researcher'.
    - If findings are present or mode is copywriting (email/task_list), routes to 'writer'.
    - If general chat, routes directly to final output.
    """
    logger.info("Supervisor Node: Analyzing routing path...")
    
    event_queue = config.get("configurable", {}).get("event_queue") if config else None
    if event_queue:
        await event_queue.put({"type": "status", "agent": "supervisor", "message": "Analyzing request routing path..."})
    
    # Configure Memori attribution to scope long-term memories to the current user
    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")
        
    messages = state["messages"]
    latest_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    # If the user selected a specific button mode or requested it in the message
    mode = state.get("mode", "general")
    
    # 1. Routing for Research Mode
    if mode == "research" and not state.get("research_findings"):
        if event_queue:
            await event_queue.put({"type": "status", "agent": "supervisor", "message": "Research Mode active: formulating search query..."})
        
        # Let LLM formulate a clean search query based on the user request
        prompt_tmpl = PromptService.get_prompt("supervisor.yaml", "research_query")
        prompt = prompt_tmpl.format(latest_user_message=latest_user_message)
        try:
            response = await async_openai_client.chat.completions.create(
                model=MODEL_FAST,
                messages=[
                    {"role": "system", "content": "You are the supervisor of a Business Research Copilot."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            res_data = json.loads(response.choices[0].message.content)
            search_query = res_data.get("search_query", latest_user_message)
            logger.info(f"Supervisor routed to RESEARCHER with query: {search_query}")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "supervisor", "message": f"Routing to Researcher with query: '{search_query}'"})
            return {
                "next_step": "researcher",
                "research_query": search_query
            }
        except Exception as e:
            logger.error(f"Error in Supervisor formulating search query: {e}")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "supervisor", "message": "Failed query formulation; routing to Researcher with raw user input"})
            return {
                "next_step": "researcher",
                "research_query": latest_user_message
            }
            
    # 2a. Task List mode without research context — run researcher first to gather company intelligence.
    # This ensures the checklist is grounded in real company data (e.g. product priorities, recent news)
    # rather than being a generic template.
    if mode == "task_list" and not state.get("research_findings"):
        if event_queue:
            await event_queue.put({"type": "status", "agent": "supervisor", "message": "Task List mode: no company research found — gathering intelligence first..."})
        prompt_tmpl = PromptService.get_prompt("supervisor.yaml", "research_query")
        prompt = prompt_tmpl.format(latest_user_message=latest_user_message)
        try:
            response = await async_openai_client.chat.completions.create(
                model=MODEL_FAST,
                messages=[
                    {"role": "system", "content": "You are the supervisor of a Business Research Copilot."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            res_data = json.loads(response.choices[0].message.content)
            search_query = res_data.get("search_query", latest_user_message)
            logger.info(f"Task list mode: routing to RESEARCHER first with query: {search_query}")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "supervisor", "message": f"Researching company context for task list: '{search_query}'"})
            return {
                "next_step": "researcher",
                "research_query": search_query
            }
        except Exception as e:
            logger.error(f"Task list supervisor: failed to formulate search query: {e}")
            # Fall through to writer even without research context

    # 2b. Routing for Copywriting Modes (Email / Task List) when research is already done,
    # or for email_draft which uses whatever context is already in the conversation.
    if mode in ["email_draft", "task_list"] or state.get("research_findings"):
        logger.info(f"Supervisor routed to WRITER (Mode: {mode})")
        if event_queue:
            await event_queue.put({"type": "status", "agent": "supervisor", "message": f"Directing to Writer agent for mode: {mode}"})
        return {"next_step": "writer"}
        
    # 3. Standard Chat routing
    # Check if the text naturally asks about a company requiring research
    prompt_tmpl = PromptService.get_prompt("supervisor.yaml", "classify_intent")
    prompt = prompt_tmpl.format(latest_user_message=latest_user_message)
    try:
        response = await async_openai_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": "You are the supervisor of a Business Research Copilot."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        res_data = json.loads(response.choices[0].message.content)
        if res_data.get("needs_research", False):
            search_query = res_data.get("search_query", latest_user_message)
            logger.info(f"Supervisor detected research intent. Routing to RESEARCHER: {search_query}")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "supervisor", "message": f"Detected research intent; routing to Researcher with query: '{search_query}'"})
            return {
                "next_step": "researcher",
                "research_query": search_query,
                "mode": "research"
            }
    except Exception as e:
        logger.error(f"Error in intent classifier: {e}")
        
    # Default to directly generating a response for conversational chat
    logger.info("Supervisor routed to direct response (conversational chat)")
    if event_queue:
        await event_queue.put({"type": "status", "agent": "supervisor", "message": "Routing to Writer for conversational reply..."})
    return {"next_step": "writer"}


