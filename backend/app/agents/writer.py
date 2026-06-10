import time
import logging
import asyncio
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

# Use gemini-2.5-flash for all writer completions.
# flash has a much more generous free-tier quota than pro and produces
# high-quality structured business drafts suitable for this use case.
MODEL = "gemini-2.5-flash"
logger.info("Writer Agent initialized using Gemini Client (model: %s).", MODEL)

mem_client = MemoryService.register_client(openai_client)
async_mem_client = MemoryService.register_client(async_openai_client)



async def _completion_with_retry_stream(messages: list, event_queue=None, max_attempts: int = 3) -> str:
    """
    Call the LLM with exponential backoff on 429 (rate-limit) errors.
    Streams back content chunks to the event_queue, and returns full accumulated text.
    """
    delay = 35  # initial wait in seconds on a 429
    for attempt in range(1, max_attempts + 1):
        try:
            response = await async_openai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
                stream=True,
                timeout=30.0
            )
            full_text = ""
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                if content:
                    full_text += content
                    if event_queue:
                        await event_queue.put({"type": "token", "content": content})
            return full_text
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < max_attempts:
                logger.warning(
                    "Writer Node: Rate-limited (attempt %d/%d) during streaming. Waiting %ds before retry...",
                    attempt, max_attempts, delay,
                )
                await asyncio.sleep(delay)
                delay = int(delay * 1.5)  # exponential backoff
            else:
                raise
    raise RuntimeError("Writer: all streaming retry attempts exhausted.")


async def writer_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """
    Writer Agent: Synthesizes chat history, research findings, and target mode
    to draft structured business outputs.
    """
    logger.info("Writer Node: Generating draft copy...")
    
    event_queue = config.get("configurable", {}).get("event_queue") if config else None
    if event_queue:
        await event_queue.put({"type": "status", "agent": "writer", "message": "Writer agent is composing the business draft..."})

    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")
    if hasattr(async_mem_client, "attribution"):
        async_mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")

    mode = state.get("mode", "general")
    findings = state.get("research_findings", [])
    messages = state["messages"]
    feedback = state.get("feedback")

    # Format research context for prompt
    research_context = ""
    if findings:
        research_context = "### Web Search Research Findings:\n"
        for idx, f in enumerate(findings):
            research_context += (
                f"Source [{idx+1}]: {f['title']}\n"
                f"URL: {f['link']}\n"
                f"Snippet: {f['snippet']}\n"
                f"Clean Web Content: {f['raw_content'][:2000]}\n"
                f"-----------------------------------------\n"
            )

    # Build prompt based on mode using PromptService
    system_prompt = PromptService.get_prompt("writer.yaml", mode)

    # If Judge has returned feedback for correction
    if feedback:
        self_corr_tmpl = PromptService.get_prompt("writer.yaml", "self_correction")
        system_prompt += self_corr_tmpl.format(feedback=feedback)

    # Build prompt sequence
    prompt_messages = [
        {"role": "system", "content": system_prompt}
    ]


    # Inject research findings as background knowledge
    if research_context:
        prompt_messages.append({"role": "system", "content": research_context})

    # ── Memory Injection ──────────────────────────────────────────────────────
    # Inject the user's long-term memory facts (name, title, company, preferences)
    # so the model can personalise output without asking the user to repeat them.
    user_memory_context = state.get("user_memory_context")
    if user_memory_context:
        prompt_messages.append({"role": "system", "content": user_memory_context})
        logger.info("Writer Node: Injected user memory context into prompt.")
    # ──────────────────────────────────────────────────────────────────────────

    # Append the actual conversation context
    for msg in messages:
        prompt_messages.append({"role": msg["role"], "content": msg["content"]})

    # Ensure there is at least one user message to satisfy Gemini requirements
    has_user = any(m["role"] == "user" for m in prompt_messages)
    if not has_user:
        prompt_messages.append({"role": "user", "content": "Please draft the response based on the system instructions."})

    try:
        # Signal start of streamed content to the client
        if event_queue:
            await event_queue.put({"type": "stream_start"})
            
        draft = await _completion_with_retry_stream(prompt_messages, event_queue=event_queue)
        
        # Signal end of streamed content to the client
        if event_queue:
            await event_queue.put({"type": "stream_end"})
            
        logger.info("Writer Node: Draft generated successfully.")
        return {
            "draft": draft,
            "next_step": "judge"
        }
    except Exception as e:
        logger.error("Error in Writer Node completion: %s", e)
        if event_queue:
            await event_queue.put({"type": "stream_end"})
        return {
            "draft": "[System Error: Writer failed to compile draft. Please try again.]",
            "next_step": "judge"
        }

