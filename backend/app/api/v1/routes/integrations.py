import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.v1.routes.auth import get_current_user
from app.models.user import User
from app.schemas.integration import (
    GmailSendRequest,
    GmailSendResponse,
    GmailStatusResponse,
    GmailConnectResponse,
)
from app.services.gmail_service import GmailService
from app.core.config import settings
from app.services.prompt_service import PromptService
from pydantic import BaseModel
from openai import AsyncOpenAI

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_composio_configured():
    """Raise 503 if the Composio API key is not set."""
    if not settings.COMPOSIO_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gmail integration is not configured. "
                "Please set COMPOSIO_API_KEY in the backend environment."
            ),
        )


# ── GET /integrations/gmail/status ──────────────────────────────────────────

@router.get(
    "/gmail/status",
    response_model=GmailStatusResponse,
    summary="Check whether the current user's Gmail account is connected via Composio",
)
def gmail_status(current_user: User = Depends(get_current_user)):
    """
    Returns { connected: true } if the user has an active Gmail OAuth connection,
    { connected: false } otherwise. Never raises an error — safe to poll on page load.
    """
    if not settings.COMPOSIO_API_KEY:
        return GmailStatusResponse(connected=False)

    svc = GmailService()
    connected = svc.is_connected(str(current_user.id))
    return GmailStatusResponse(connected=connected)


# ── GET /integrations/gmail/connect ─────────────────────────────────────────

@router.get(
    "/gmail/connect",
    response_model=GmailConnectResponse,
    summary="Initiate Gmail OAuth via Composio — returns the redirect URL",
)
def gmail_connect(current_user: User = Depends(get_current_user)):
    """
    Generates a Composio-managed OAuth redirect URL for Gmail.
    The frontend should open this URL (or redirect to it) so the user
    can authorise access. After authorisation Composio stores the token.
    """
    _check_composio_configured()
    svc = GmailService()
    try:
        redirect_url = svc.get_connection_url(str(current_user.id))
        return GmailConnectResponse(redirect_url=redirect_url)
    except Exception as e:
        logger.error("gmail_connect: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate Gmail connection URL: {e}",
        )


# ── POST /integrations/gmail/send ────────────────────────────────────────────

@router.post(
    "/gmail/send",
    response_model=GmailSendResponse,
    status_code=status.HTTP_200_OK,
    summary="Send an email from the user's connected Gmail account",
)
def gmail_send(
    payload: GmailSendRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Executes the Composio GMAIL_SEND_EMAIL action for the authenticated user.
    Requires the user to have previously connected their Gmail account via
    GET /integrations/gmail/connect.
    """
    _check_composio_configured()
    svc = GmailService()

    if not svc.is_connected(str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Gmail account not connected. "
                "Please connect your Gmail first via /integrations/gmail/connect."
            ),
        )

    try:
        svc.send_email(
            user_id=str(current_user.id),
            to=str(payload.to),
            subject=payload.subject,
            body=payload.body,
            cc=payload.cc,
        )
        return GmailSendResponse(
            success=True,
            message=f"Email sent successfully to {payload.to}",
        )
    except Exception as e:
        logger.error("gmail_send: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send email: {e}",
        )


# ── POST /integrations/gmail/parse-draft ─────────────────────────────────────

class ParseDraftRequest(BaseModel):
    draft: str  # Raw email draft text from the LLM


class ParseDraftResponse(BaseModel):
    subject: str
    body: str


# Reuse the same Gemini client pattern as the rest of the backend
_api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY
if not _api_key or _api_key.startswith("your-"):
    _api_key = "dummy-api-key"

_parse_client = AsyncOpenAI(
    api_key=_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)


@router.post(
    "/gmail/parse-draft",
    response_model=ParseDraftResponse,
    summary="Parse an LLM email draft into structured subject + body fields",
)
async def gmail_parse_draft(
    payload: ParseDraftRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Uses the email_parse prompt to extract a clean subject line and body
    from a raw LLM-generated email draft.
    The frontend calls this when the user clicks 'Send via Gmail' to pre-fill
    the send confirmation modal.
    """
    try:
        prompt_tmpl = PromptService.get_prompt("writer.yaml", "email_parse")
        prompt = prompt_tmpl.format(draft=payload.draft)

        response = await _parse_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": "You are a precise JSON-only email parser."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(response.choices[0].message.content)
        return ParseDraftResponse(
            subject=data.get("subject", "Outreach Email"),
            body=data.get("body", payload.draft),
        )
    except Exception as e:
        logger.warning("gmail_parse_draft fallback due to error: %s", e)
        # Graceful fallback — return draft as-is with a generic subject
        first_line = payload.draft.split("\n")[0][:80] if payload.draft else "Outreach Email"
        return ParseDraftResponse(subject=first_line, body=payload.draft)

