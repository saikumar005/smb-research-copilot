import time
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

# Use gemini-2.5-flash for all writer completions.
# flash has a much more generous free-tier quota than pro and produces
# high-quality structured business drafts suitable for this use case.
MODEL = "gemini-2.5-flash"
logger.info("Writer Agent initialized using Gemini Client (model: %s).", MODEL)

mem_client = MemoryService.register_client(openai_client)


def _completion_with_retry(messages: list, max_attempts: int = 3) -> str:
    """
    Call the LLM with exponential backoff on 429 (rate-limit) errors.
    Returns the text content of the first choice.
    """
    delay = 35  # initial wait in seconds on a 429
    for attempt in range(1, max_attempts + 1):
        try:
            response = openai_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt < max_attempts:
                logger.warning(
                    "Writer Node: Rate-limited (attempt %d/%d). Waiting %ds before retry...",
                    attempt, max_attempts, delay,
                )
                time.sleep(delay)
                delay = int(delay * 1.5)  # exponential backoff
            else:
                raise
    raise RuntimeError("Writer: all retry attempts exhausted.")


def writer_node(state: AgentState) -> dict:
    """
    Writer Agent: Synthesizes chat history, research findings, and target mode
    to draft structured business outputs.
    """
    logger.info("Writer Node: Generating draft copy...")

    if hasattr(mem_client, "attribution"):
        mem_client.attribution(entity_id=str(state["user_id"]), process_id="research_copilot")

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

    # Build prompt based on mode
    system_prompt = ""
    if mode == "research":
        system_prompt = (
            "You are a Senior Business Analyst. Your goal is to draft a comprehensive Company Brief.\n"
            "You must follow this exact output structure:\n"
            "1. **Company Overview**: A concise summary of the business, its size, domain, and core value proposition.\n"
            "2. **Key Findings**: Important recent announcements, products, or developments found in search results.\n"
            "3. **Likely Priorities & Pain Points**: Analytical assessment of what this business is prioritizing or struggling with.\n"
            "4. **Suggested Outreach Angle**: Practical angle for sales or collaboration outreach.\n"
            "5. **Sources**: Clickable markdown links to the sources used, formatted exactly as: `[1] [Source Title](URL) - snippet summary`.\n\n"
            "Be analytical, professional, and write for non-technical business users."
        )
    elif mode == "email_draft":
        system_prompt = (
            "You are a sales copywriting expert. Write a highly tailored sales outreach email.\n"
            "It should be concise (under 250 words), structured with clear spacing, professional yet engaging, "
            "and leverage the company findings and user criteria. Do not use generic buzzwords. "
            "Incorporate a soft call-to-action."
        )
    elif mode == "task_list":
        system_prompt = (
            "You are a Business Operations Consultant. Write a structured follow-up task list.\n"
            "Format the output as a clean checklist using `- [ ]` syntax.\n"
            "Group tasks logically (e.g., Preparation, Customization, Outreach, Follow-up) and give actionable, concrete instructions."
        )
    else:
        system_prompt = (
            "You are a Business Research Copilot. Answer the user's message conversationally.\n"
            "Be professional, direct, and leverage any available web research context if helpful."
        )

    # If Judge has returned feedback for correction
    if feedback:
        system_prompt += (
            f"\n\n### CRITICAL: Self-Correction Request\n"
            f"Your previous draft was rejected by the LLM Judge. Please revise it to address this feedback:\n"
            f"'{feedback}'\n"
            f"Do not make the same mistakes."
        )

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
        draft = _completion_with_retry(prompt_messages)
        logger.info("Writer Node: Draft generated successfully.")
        return {
            "draft": draft,
            "next_step": "judge"
        }
    except Exception as e:
        logger.error("Error in Writer Node completion: %s", e)
        return {
            "draft": "[System Error: Writer failed to compile draft. Please try again.]",
            "next_step": "judge"
        }
