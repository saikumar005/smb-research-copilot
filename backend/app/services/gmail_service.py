"""
GmailService — Composio SDK v0.13.x implementation.

Composio v0.13.x uses a "Tool Router Session" paradigm:
  1. composio.create(user_id=..., toolkits=['gmail'])  → ToolRouterSession
  2. session.authorize('gmail')                         → ConnectionRequest (OAuth URL)
  3. session.execute('GMAIL_SEND_EMAIL', arguments={})  → direct tool execution

The older patterns (connected_accounts.initiate, tools.get().invoke) no longer work.
"""
import logging
from typing import Optional

from composio import Composio
from app.core.config import settings

logger = logging.getLogger(__name__)

# Composio toolkit slug — must be lowercase for the session API
_GMAIL_TOOLKIT = "gmail"
# Tool slug for sending emails
_SEND_EMAIL_TOOL = "GMAIL_SEND_EMAIL"


class GmailService:
    """
    Wrapper around the Composio SDK (v0.13.x) for Gmail OAuth and email sending.

    Key v0.13.x APIs used:
    - composio.create(user_id, toolkits=[...])   → creates a ToolRouterSession
    - session.authorize(toolkit)                  → starts OAuth flow, returns redirect URL
    - session.execute(tool_slug, arguments={...}) → executes a Gmail tool directly
    - composio.connected_accounts.list(...)       → checks connection status
    """

    def __init__(self):
        if not settings.COMPOSIO_API_KEY:
            logger.warning(
                "GmailService: COMPOSIO_API_KEY is not set. "
                "Gmail integration will be unavailable."
            )
        # No provider needed — we use the session.execute() path, not provider tools
        self._composio = Composio(api_key=settings.COMPOSIO_API_KEY or None)

    def _create_session(self, user_id: str):
        """Create a Tool Router session scoped to Gmail for the given user."""
        return self._composio.create(
            user_id=user_id,
            toolkits=[_GMAIL_TOOLKIT],
        )

    # ── Connection management ────────────────────────────────────────────────

    def get_connection_url(self, user_id: str) -> str:
        """
        Initiate Gmail OAuth for the user via Composio Tool Router.
        Returns the OAuth redirect URL the frontend should open.
        """
        try:
            session = self._create_session(user_id)
            connection_request = session.authorize(_GMAIL_TOOLKIT)

            redirect_url = getattr(connection_request, "redirect_url", None)
            if not redirect_url:
                raise RuntimeError(
                    f"No redirect_url in connection request. Got: {connection_request}"
                )
            logger.info("GmailService: OAuth URL generated for user=%s", user_id)
            return redirect_url
        except Exception as e:
            logger.error("GmailService: Failed to generate OAuth URL: %s", e)
            raise

    def is_connected(self, user_id: str) -> bool:
        """
        Returns True if the user has at least one active Gmail connection in Composio.
        """
        try:
            result = self._composio.connected_accounts.list(
                user_ids=[user_id],
                toolkit_slugs=[_GMAIL_TOOLKIT],
                statuses=["ACTIVE"],
            )
            items = getattr(result, "items", result) or []
            connected = len(list(items)) > 0
            logger.debug(
                "GmailService: is_connected user=%s → %s", user_id, connected
            )
            return connected
        except Exception as e:
            logger.warning("GmailService: is_connected check failed: %s", e)
            return False

    # ── Email operations ─────────────────────────────────────────────────────

    def send_email(
        self,
        user_id: str,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
    ) -> dict:
        """
        Send an email from the user's connected Gmail account.

        Uses session.execute() which is the correct v0.13.x path for
        direct tool execution without an LLM agent in the loop.

        Args:
            user_id:  App-level user ID (scopes the Composio connection)
            to:       Recipient email address
            subject:  Email subject line
            body:     Plain-text or HTML email body
            cc:       Optional CC address (comma-separated string)

        Returns:
            Dict with the Composio execution result.

        Raises:
            RuntimeError on tool execution failure.
        """
        try:
            session = self._create_session(user_id)

            arguments: dict = {
                "recipient_email": to,
                "subject": subject,
                "body": body,
            }
            if cc:
                arguments["cc"] = cc

            result = session.execute(
                _SEND_EMAIL_TOOL,
                arguments=arguments,
            )

            # SessionExecuteResponse has .data, .error, .log_id attributes
            error = getattr(result, "error", None)
            if error:
                raise RuntimeError(f"Composio returned error: {error}")

            data = getattr(result, "data", result)
            logger.info(
                "GmailService: Email sent to=%s subject=%s user=%s",
                to,
                subject,
                user_id,
            )
            return data if isinstance(data, dict) else {"output": str(data)}

        except Exception as e:
            logger.error("GmailService: send_email failed: %s", e)
            raise
