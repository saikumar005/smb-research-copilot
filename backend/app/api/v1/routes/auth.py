"""
Authentication Routes
---------------------
Handles all authentication flows:
  - Email/password signup, login, forgot-password, reset-password
  - Google SSO via ID token verification (GIS popup flow)
  - Current user profile retrieval

The get_current_user dependency is also exported from here and imported by
all other routers that need to know the authenticated user.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core import security
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    Token,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    GoogleAuthRequest,
)
from app.services.auth_service import AuthService
from app.services.google_auth_service import verify_google_id_token
from app.repositories.user_repository import UserRepository
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# OAuth2 Bearer scheme — used by the get_current_user dependency
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ---------------------------------------------------------------------------
# Dependency: get_current_user
# Shared across all protected routes (chats, actions, memory, etc.)
# ---------------------------------------------------------------------------
def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolves the authenticated User from the Bearer JWT.

    The AuthMiddleware already validates the token at the HTTP layer, so by
    the time this dependency runs we know the token is valid. We still decode
    it here to look up the full User ORM object for downstream handlers.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Prefer token already verified by middleware (stored on request.state)
    user_id_str: str | None = None
    if hasattr(request.state, "user_id"):
        user_id_str = str(request.state.user_id)
    elif token:
        user_id_str = security.decode_access_token(token)

    if not user_id_str:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(user_id)
    if user is None:
        logger.warning("get_current_user: user_id=%s not found in DB", user_id)
        raise credentials_exception

    return user


# ---------------------------------------------------------------------------
# Email / Password Auth Routes
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user with email and password."""
    logger.info("Signup attempt | email=%s", user_data.email)
    try:
        user = AuthService.register_user(db, user_data)
        logger.info("Signup successful | user_id=%s email=%s", user.id, user.email)
        return user
    except ValueError as e:
        logger.warning("Signup rejected | email=%s reason=%s", user_data.email, e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password, returns a JWT."""
    logger.info("Login attempt | email=%s", login_data.email)
    user = AuthService.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        logger.warning("Login failed — invalid credentials | email=%s", login_data.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = security.create_access_token(subject=user.id)
    logger.info("Login successful | user_id=%s email=%s", user.id, user.email)
    return Token(access_token=access_token, auth_provider="email")


@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Initiates password reset. Always returns success to prevent email enumeration.
    Reset token is printed to server logs for local development simulation.
    """
    logger.info("Forgot-password requested | email=%s", request.email)
    AuthService.generate_password_reset_token(db, request.email)
    return {"message": "If the email is registered, a password reset link has been logged to the server console."}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Resets a user's password using a valid reset token."""
    success = AuthService.reset_password(db, request.token, request.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    logger.info("Password reset completed via token.")
    return {"message": "Password reset successfully."}


# ---------------------------------------------------------------------------
# Google OAuth SSO Route
# ---------------------------------------------------------------------------

@router.post("/google", response_model=Token, status_code=status.HTTP_200_OK)
def google_sso(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """
    Authenticate via Google Identity Services popup flow.

    Accepts a Google ID token from the frontend, verifies it server-side using
    google-auth, then:
      1. Finds existing user by google_id  → issue JWT immediately
      2. Finds existing user by email      → link google_id + issue JWT
      3. Neither found                     → create new user + issue JWT

    This endpoint is intentionally on the PUBLIC_PATHS whitelist in AuthMiddleware
    so unauthenticated users can reach it.
    """
    logger.info("Google SSO: token exchange initiated")

    # Verify the ID token with Google's public keys
    google_user = verify_google_id_token(payload.id_token)
    if not google_user:
        logger.warning("Google SSO: rejected invalid/expired ID token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google ID token verification failed. The token may be expired or tampered.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(db)

    # --- Case 1: returning Google user ---
    existing_user = user_repo.get_by_google_id(google_user.google_id)
    if existing_user:
        logger.info(
            "Google SSO: returning user | user_id=%s email=%s",
            existing_user.id, existing_user.email,
        )
        access_token = security.create_access_token(subject=existing_user.id)
        return Token(access_token=access_token, auth_provider="google")

    # --- Case 2: email already registered (link accounts) ---
    email_user = user_repo.get_by_email(google_user.email)
    if email_user:
        logger.info(
            "Google SSO: linking google_id to existing email user | user_id=%s email=%s",
            email_user.id, email_user.email,
        )
        user_repo.link_google_id(email_user, google_user.google_id)
        access_token = security.create_access_token(subject=email_user.id)
        return Token(access_token=access_token, auth_provider="google")

    # --- Case 3: new user — auto-register ---
    new_user = user_repo.create_google_user(
        email=google_user.email,
        name=google_user.name,
        google_id=google_user.google_id,
    )
    logger.info(
        "Google SSO: created new user | user_id=%s email=%s name=%s",
        new_user.id, new_user.email, new_user.name,
    )
    access_token = security.create_access_token(subject=new_user.id)
    return Token(access_token=access_token, auth_provider="google")


# ---------------------------------------------------------------------------
# Authenticated Profile Route
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile."""
    return current_user
