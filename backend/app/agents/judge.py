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

openai_client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
async_openai_client = AsyncOpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
MODEL_FAST = "gemini-2.5-flash"
logger.info("Judge Agent initialized using Gemini Client.")

mem_client = MemoryService.register_client(openai_client)
async_mem_client = MemoryService.register_client(async_openai_client)

async def judge_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """
    LLM-as-a-Judge Node:
    - Evaluates Writer drafts against quality rules.
    - If fail and critic_loops < 3: sets next_step = 'writer', increments loop count, writes feedback.
    - If pass or loop count limit reached: sets next_step = 'end' and copies draft to final_response.
    """
    logger.info("Judge Node: Evaluating draft output...")
    
    event_queue = config.get("configurable", {}).get("event_queue") if config else None
    if event_queue:
        await event_queue.put({"type": "status", "agent": "judge", "message": "Judge node is validating quality criteria..."})
    
    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")
        
    draft = state.get("draft", "")
    mode = state.get("mode", "general")
    critic_loops = state.get("critic_loops", 0)
    findings = state.get("research_findings", [])
    
    # Fast exit if loop limit hit (max 1 correction cycle = 2 writer attempts total)
    if critic_loops >= 1:
        logger.warning("Judge Node: Maximum critic loops reached. Forced passing the current draft.")
        if event_queue:
            await event_queue.put({"type": "status", "agent": "judge", "message": "Maximum self-correction cycles reached; forcing response delivery."})
        return {
            "next_step": "end",
            "final_response": draft,
            "feedback": None
        }
        
    # Build criteria explanation using PromptService
    try:
        criteria = PromptService.get_prompt("judge.yaml", f"criteria_{mode}")
    except KeyError:
        criteria = PromptService.get_prompt("judge.yaml", "criteria_general")

    judge_prompt_tmpl = PromptService.get_prompt("judge.yaml", "judge_prompt")
    judge_prompt = judge_prompt_tmpl.format(criteria=criteria, draft=draft)
    system_prompt = PromptService.get_prompt("judge.yaml", "system_prompt")
    
    try:
        response = await async_openai_client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": judge_prompt}
            ],
            response_format={"type": "json_object"},
            timeout=30.0
        )
        res_data = json.loads(response.choices[0].message.content)
        passed = res_data.get("passed", True)
        feedback = res_data.get("feedback", "")
        
        if passed:
            logger.info("Judge Node: Draft passed validation!")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "judge", "message": "Draft passed all quality checklist rules successfully."})
            return {
                "next_step": "end",
                "final_response": draft,
                "feedback": None
            }
        else:
            logger.warning(f"Judge Node: Draft failed validation (Loop {critic_loops + 1}). Feedback: {feedback}")
            if event_queue:
                await event_queue.put({"type": "status", "agent": "judge", "message": f"Validation failed: {feedback}. Triggering self-correction..."})
            return {
                "next_step": "writer",
                "feedback": feedback,
                "critic_loops": critic_loops + 1
            }
    except Exception as e:
        logger.error(f"Error in Judge Node execution: {e}")
        if event_queue:
            await event_queue.put({"type": "status", "agent": "judge", "message": "QA Judge system error; delivering draft as fallback."})
        # Default to pass in case of system issues to avoid blocking the user
        return {
            "next_step": "end",
            "final_response": draft,
            "feedback": None
        }

