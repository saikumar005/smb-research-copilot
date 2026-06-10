"""
Authentication Middleware
-------------------------
Production-grade Starlette middleware that enforces JWT authentication at the
HTTP layer — before any route handler executes.

Design decisions:
  - Applied globally on every request so no route can accidentally be left unprotected.
  - Public routes are explicitly whitelisted in PUBLIC_PATHS.
  - 401 responses include a structured JSON body (not plain text).
  - Every auth decision is logged at INFO or WARNING level for audit trails.
  - Token decoding errors (expired, tampered) are caught and logged with the
    client IP so suspicious patterns can be identified.
"""
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core import security

logger = logging.getLogger(__name__)

# Routes that do NOT require a valid JWT.
# All other /api/v1/* routes are automatically protected.
PUBLIC_PATHS: set[str] = {
    # Auth endpoints
    "/api/v1/auth/login",
    "/api/v1/auth/signup",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    # Google SSO — must be public so unauthenticated users can log in
    "/api/v1/auth/google",
    # Health check — used by load balancers / Docker health probes
    "/health",
    # OpenAPI docs (disable in prod by removing from here + setting openapi_url=None)
    "/api/v1/openapi.json",
    "/docs",
    "/redoc",
}

# HTTP methods that are considered safe and never carry sensitive mutations.
# OPTIONS is always allowed (CORS pre-flight).
SAFE_METHODS: set[str] = {"OPTIONS"}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Validates the Bearer JWT on every protected route.

    Flow:
      1. Allow SAFE_METHODS (OPTIONS) through immediately.
      2. Allow PUBLIC_PATHS through without a token.
      3. Extract Bearer token from Authorization header.
      4. Decode and validate the JWT.
      5. Attach `request.state.user_id` for downstream handlers.
      6. Reject with 401 JSON on any failure.
    """

    async def dispatch(self, request: Request, call_next):
        # Always allow pre-flight CORS requests
        if request.method in SAFE_METHODS:
            return await call_next(request)

        path = request.url.path

        # Allow public paths without authentication
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Extract Authorization header
        auth_header: Optional[str] = request.headers.get("Authorization")
        client_ip = request.client.host if request.client else "unknown"

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning(
                "Auth middleware: Missing/malformed Authorization header | "
                "path=%s method=%s ip=%s",
                path, request.method, client_ip,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Authentication required. Please provide a valid Bearer token.",
                    "code": "MISSING_TOKEN",
                },
            )

        token = auth_header.split(" ", 1)[1]
        user_id_str = security.decode_access_token(token)

        if user_id_str is None:
            logger.warning(
                "Auth middleware: Invalid/expired JWT | "
                "path=%s method=%s ip=%s",
                path, request.method, client_ip,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Token is invalid or has expired. Please log in again.",
                    "code": "INVALID_TOKEN",
                },
            )

        # Attach decoded user ID to request state for use in route dependencies
        try:
            request.state.user_id = int(user_id_str)
        except ValueError:
            logger.error(
                "Auth middleware: JWT sub is not a valid integer | sub=%s ip=%s",
                user_id_str, client_ip,
            )
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Malformed token payload.",
                    "code": "MALFORMED_TOKEN",
                },
            )

        logger.debug(
            "Auth middleware: Authenticated user_id=%s | path=%s method=%s ip=%s",
            request.state.user_id, path, request.method, client_ip,
        )

        return await call_next(request)
