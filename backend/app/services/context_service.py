"""
Context Extraction Service
--------------------------
Scans recent chat messages using a lightweight LLM call to determine:
  - Whether a company name has been mentioned or researched
  - Whether enough context exists to auto-execute an action mode
  - Which required fields are still missing

This keeps all guard-rail logic server-side so the frontend only needs
to call /actions/validate and act on the structured response.
"""
import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Re-use gemini-flash for fast, cheap context extraction
api_key = settings.GEMINI_API_KEY
if not api_key or api_key.startswith("your-"):
    api_key = settings.OPENAI_API_KEY

if not api_key:
    api_key = "dummy-api-key"

_client = OpenAI(
    api_key=api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
MODEL = "gemini-2.5-flash"

# Required fields per action mode
MODE_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "research": ["company_name"],
    "email_draft": ["company_name"],
    "task_list": ["company_name"],
}

# Human-readable labels for missing field messages
FIELD_LABELS: Dict[str, str] = {
    "company_name": "the target company name",
}


def extract_chat_context(
    messages: List[Dict[str, str]],
    mode: str,
) -> Dict[str, Any]:
    """
    Scans the last 15 messages of a chat thread and uses Gemini to extract
    whether the required context is available to auto-execute the given action mode.

    Returns a dict with keys:
        can_execute (bool)
        company_name (str | None)
        context_summary (str | None)
        missing_fields (list[str])
        auto_message (str | None)
    """
    required = MODE_REQUIRED_FIELDS.get(mode, ["company_name"])

    # Take the last 15 messages to limit token usage
    recent = messages[-15:] if len(messages) > 15 else messages

    # Build a compact conversation transcript for the LLM
    transcript_lines = []
    for m in recent:
        role = m.get("role", "unknown").upper()
        content = (m.get("content") or "")[:800]  # cap per message
        transcript_lines.append(f"[{role}]: {content}")
    transcript = "\n".join(transcript_lines)

    if not transcript.strip():
        return _missing_response(required)

    system_prompt = (
        "You are a context extraction assistant for a Business Research Copilot.\n"
        "Your task: read the conversation transcript and extract structured information.\n"
        "Return ONLY a valid JSON object — no markdown, no explanation.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "company_name": "<string or null>",\n'
        '  "has_prior_research": <true/false>,\n'
        '  "context_summary": "<one sentence describing what you found>"\n'
        "}\n\n"
        "Rules:\n"
        "- company_name: the most recently discussed or researched company. null if none found.\n"
        "- has_prior_research: true if the conversation contains a company research brief "
        "(headers like Company Overview, Key Findings, etc.).\n"
        "- context_summary: brief factual description of found context."
    )

    user_prompt = (
        f"Requested action mode: {mode}\n\n"
        f"Conversation transcript (most recent last):\n{transcript}"
    )

    try:
        response = _client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
    except Exception as e:
        logger.error("Context extraction LLM call failed: %s", e)
        # Fail safe: treat as missing context so the user is prompted
        return _missing_response(required)

    company_name: Optional[str] = data.get("company_name") or None
    has_prior_research: bool = bool(data.get("has_prior_research", False))
    context_summary: Optional[str] = data.get("context_summary")

    # Determine which required fields are missing
    missing: List[str] = []
    if "company_name" in required and not company_name:
        missing.append("company_name")

    can_execute = len(missing) == 0

    # Build the auto_message the frontend should pass to /actions/run
    auto_message = None
    if can_execute:
        auto_message = _build_auto_message(mode, company_name, has_prior_research)

    logger.info(
        "Context check for mode=%s: can_execute=%s company=%s missing=%s",
        mode, can_execute, company_name, missing,
    )

    return {
        "can_execute": can_execute,
        "company_name": company_name,
        "context_summary": context_summary,
        "missing_fields": missing,
        "auto_message": auto_message,
    }


def _missing_response(required: List[str]) -> Dict[str, Any]:
    return {
        "can_execute": False,
        "company_name": None,
        "context_summary": None,
        "missing_fields": list(required),
        "auto_message": None,
    }


def _build_auto_message(mode: str, company_name: Optional[str], has_prior_research: bool) -> str:
    """
    Constructs the message string that /actions/run will receive when auto-executing.
    """
    company = company_name or "the company"
    if mode == "research":
        return f"Research {company} and provide a full company brief with outreach angles."
    elif mode == "email_draft":
        context = " Use the research findings already in this conversation as context." if has_prior_research else ""
        return f"Draft a personalized cold sales outreach email for {company}.{context}"
    elif mode == "task_list":
        context = " Incorporate insights from the research already done in this chat." if has_prior_research else ""
        return f"Create an actionable task checklist to prepare for outreach to {company}.{context}"
    return f"Execute {mode} for {company}."
