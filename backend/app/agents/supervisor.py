import json
import logging
from openai import OpenAI
from app.core.config import settings
from app.services.memory_service import MemoryService
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

# Initialize Gemini client unconditionally (using GEMINI_API_KEY or falling back to OPENAI_API_KEY)
api_key = settings.GEMINI_API_KEY
if not api_key or api_key.startswith("your-"):
    api_key = settings.OPENAI_API_KEY

openai_client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
MODEL_FAST = "gemini-2.5-flash"
MODEL_SMART = "gemini-2.5-pro"
logger.info("Supervisor Agent initialized using Gemini Client.")

mem_client = MemoryService.register_client(openai_client)

def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor Agent analyzes user input and state to determine the routing path:
    - If live info is needed or mode is 'research', routes to 'researcher'.
    - If findings are present or mode is copywriting (email/task_list), routes to 'writer'.
    - If general chat, routes directly to final output.
    """
    logger.info("Supervisor Node: Analyzing routing path...")
    
    # Configure Memori attribution to scope long-term memories to the current user
    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")
        
    messages = state["messages"]
    latest_user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    
    # If the user selected a specific button mode or requested it in the message
    mode = state.get("mode", "general")
    
    # 1. Routing for Research Mode
    if mode == "research" and not state.get("research_findings"):
        # Let LLM formulate a clean search query based on the user request
        prompt = (
            f"You are the supervisor of a Business Research Copilot. The user requested company research.\n"
            f"User input: '{latest_user_message}'\n\n"
            f"Respond with a JSON object containing the key 'search_query' representing the best search term to query Google/DuckDuckGo."
        )
        try:
            response = openai_client.chat.completions.create(
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
            return {
                "next_step": "researcher",
                "research_query": search_query
            }
        except Exception as e:
            logger.error(f"Error in Supervisor formulating search query: {e}")
            return {
                "next_step": "researcher",
                "research_query": latest_user_message
            }
            
    # 2. Routing for Copywriting Modes (Email / Task List / Summarization)
    if mode in ["email_draft", "task_list"] or state.get("research_findings"):
        logger.info(f"Supervisor routed to WRITER (Mode: {mode})")
        return {"next_step": "writer"}
        
    # 3. Standard Chat routing
    # Check if the text naturally asks about a company requiring research
    prompt = (
        f"Analyze the user's message. Does answering it require searching the web for real-time company details?\n"
        f"User message: '{latest_user_message}'\n\n"
        f"Respond with a JSON object: {{'needs_research': true/false, 'search_query': 'clean search query if true'}}"
    )
    try:
        response = openai_client.chat.completions.create(
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
            return {
                "next_step": "researcher",
                "research_query": search_query,
                "mode": "research"
            }
    except Exception as e:
        logger.error(f"Error in intent classifier: {e}")
        
    # Default to directly generating a response for conversational chat
    logger.info("Supervisor routed to direct response (conversational chat)")
    return {"next_step": "writer"}
