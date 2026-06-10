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
logger.info("Judge Agent initialized using Gemini Client.")

mem_client = MemoryService.register_client(openai_client)

def judge_node(state: AgentState) -> dict:
    """
    LLM-as-a-Judge Node:
    - Evaluates Writer drafts against quality rules.
    - If fail and critic_loops < 3: sets next_step = 'writer', increments loop count, writes feedback.
    - If pass or loop count limit reached: sets next_step = 'end' and copies draft to final_response.
    """
    logger.info("Judge Node: Evaluating draft output...")
    
    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")
        
    draft = state.get("draft", "")
    mode = state.get("mode", "general")
    critic_loops = state.get("critic_loops", 0)
    findings = state.get("research_findings", [])
    
    # Fast exit if loop limit hit
    if critic_loops >= 2:
        logger.warning("Judge Node: Maximum critic loops reached. Forced passing the current draft.")
        return {
            "next_step": "end",
            "final_response": draft,
            "feedback": None
        }
        
    # Build criteria explanation
    criteria = ""
    if mode == "research":
        criteria = (
            "1. MUST contain these headers: 'Company Overview', 'Key Findings', 'Likely Priorities & Pain Points', 'Suggested Outreach Angle', and 'Sources'.\n"
            "2. MUST contain clickable markdown source links corresponding to search findings at the bottom in the format [Name](URL).\n"
            "3. MUST NOT contain placeholder text like '[Insert Name Here]' or empty lists."
        )
    elif mode == "email_draft":
        criteria = (
            "1. MUST be a professional sales outreach email.\n"
            "2. MUST NOT contain developer-centric terminology or raw markdown brackets for placeholders (e.g. '[your name]').\n"
            "3. MUST be concise (under 250 words) and have clean spacing."
        )
    elif mode == "task_list":
        criteria = (
            "1. MUST format items as markdown checkbox lists using '- [ ]' syntax.\n"
            "2. Tasks MUST be actionable, clear, and structured."
        )
    else:
        criteria = "1. MUST be a polite, business-friendly, and professional response."

    judge_prompt = (
        f"You are a Quality Assurance Judge for a Business Research Copilot.\n"
        f"Evaluate the generated draft according to these criteria:\n"
        f"{criteria}\n\n"
        f"Draft to evaluate:\n"
        f"\"\"\"\n{draft}\n\"\"\"\n\n"
        f"Respond with a JSON object containing:\n"
        f"{{'passed': true/false, 'feedback': 'specific corrective feedback detailing what to fix if passed is false'}}"
    )
    
    try:
        response = openai_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": "You are a Quality Assurance Judge."},
                {"role": "user", "content": judge_prompt}
            ],
            response_format={"type": "json_object"}
        )
        res_data = json.loads(response.choices[0].message.content)
        passed = res_data.get("passed", True)
        feedback = res_data.get("feedback", "")
        
        if passed:
            logger.info("Judge Node: Draft passed validation!")
            return {
                "next_step": "end",
                "final_response": draft,
                "feedback": None
            }
        else:
            logger.warning(f"Judge Node: Draft failed validation (Loop {critic_loops + 1}). Feedback: {feedback}")
            return {
                "next_step": "writer",
                "feedback": feedback,
                "critic_loops": critic_loops + 1
            }
    except Exception as e:
        logger.error(f"Error in Judge Node execution: {e}")
        # Default to pass in case of system issues to avoid blocking the user
        return {
            "next_step": "end",
            "final_response": draft,
            "feedback": None
        }
