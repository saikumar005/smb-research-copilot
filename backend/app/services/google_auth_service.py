"""
Google OAuth Token Verification Service
----------------------------------------
Verifies Google ID tokens issued by the Google Identity Services (GIS) popup flow.

Security design:
  - Uses google-auth's `id_token.verify_oauth2_token()` which validates:
      * Token signature against Google's public RSA keys (fetched from Google's JWKS endpoint)
      * Token expiry (`exp` claim)
      * Audience (`aud` claim) must match our GOOGLE_CLIENT_ID
      * Issuer (`iss` claim) must be accounts.google.com
  - Never trusts client-supplied payload — always verifies server-side.
  - Google's public keys are cached locally by the library (no per-request HTTP call).
  - All verification failures are logged with the error detail for audit trails.
"""
import logging
from typing import Optional
from dataclasses import dataclass
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.core.config import settings

logger = logging.getLogger(__name__)

# Reuse a single Google Transport requests session (thread-safe, connection-pooled)
_google_request = google_requests.Request()


@dataclass
class GoogleUserInfo:
    """Verified claims extracted from a valid Google ID token."""
    google_id: str       # The stable Google subject ID ('sub' claim)
    email: str           # Verified email address
    name: Optional[str]  # Display name (may be None if not granted)
    picture: Optional[str] = None  # Profile photo URL (not stored, for future use)


def verify_google_id_token(token: str) -> Optional[GoogleUserInfo]:
    """
    Verifies a Google ID token and extracts the user's claims.

    Returns GoogleUserInfo if valid, or None if verification fails for any reason.
    Callers should treat None as an authentication failure and return HTTP 401.

    Args:
        token: The raw ID token string from the GIS credential response.

    Returns:
        GoogleUserInfo on success, None on any verification failure.
    """
    if not settings.GOOGLE_CLIENT_ID:
        logger.error(
            "Google SSO: GOOGLE_CLIENT_ID is not configured. "
            "Set it in .env to enable Google login."
        )
        return None

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            _google_request,
            audience=settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # Covers: expired token, wrong audience, bad signature, malformed token
        logger.warning("Google SSO: ID token verification failed: %s", exc)
        return None
    except Exception as exc:
        # Network errors fetching Google's public keys, etc.
        logger.error("Google SSO: Unexpected error during token verification: %s", exc)
        return None

    # Double-check issuer (google-auth does this but be explicit)
    iss = idinfo.get("iss", "")
    if iss not in ("accounts.google.com", "https://accounts.google.com"):
        logger.warning("Google SSO: Unexpected token issuer: %s", iss)
        return None

    # email_verified must be True — reject unverified email addresses
    if not idinfo.get("email_verified", False):
        logger.warning(
            "Google SSO: Rejected token with unverified email: %s",
            idinfo.get("email"),
        )
        return None

    user_info = GoogleUserInfo(
        google_id=idinfo["sub"],
        email=idinfo["email"].lower(),
        name=idinfo.get("name"),
        picture=idinfo.get("picture"),
    )

    logger.info(
        "Google SSO: Token verified successfully | google_id=%s email=%s",
        user_info.google_id,
        user_info.email,
    )
    return user_info
