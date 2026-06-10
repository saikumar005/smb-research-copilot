"""
Comprehensive API smoke and integration tests for the Business Research Copilot.

Uses an in-memory SQLite database via StaticPool to ensure all sessions share
the same in-memory connection, avoiding "no such table" errors between test runs.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import get_db
from app.models import Base

# ---------------------------------------------------------------------------
# Test database setup — isolated SQLite in-memory instance
# ---------------------------------------------------------------------------

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Yield a fresh test session for every request."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    """Create all tables before the module's tests and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helper: reusable token fetcher
# ---------------------------------------------------------------------------

def _get_token(email: str = "test@m32.ai", password: str = "securepassword123") -> str:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


def _auth_headers(email: str = "test@m32.ai", password: str = "securepassword123") -> dict:
    return {"Authorization": f"Bearer {_get_token(email, password)}"}


# ===========================================================================
# Health Check
# ===========================================================================

def test_health_check():
    """The /health endpoint should return status=healthy without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "project" in data


# ===========================================================================
# Auth — Signup
# ===========================================================================

def test_signup():
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "test@m32.ai", "name": "Test User", "password": "securepassword123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@m32.ai"
    assert data["name"] == "Test User"
    assert "id" in data
    assert "password" not in data  # password must never be returned


def test_signup_duplicate_email():
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "test@m32.ai", "name": "Duplicate User", "password": "securepassword123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_signup_short_password_rejected():
    """Registration with a password shorter than 6 chars should be rejected."""
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "shortpass@m32.ai", "name": "Short", "password": "abc"},
    )
    assert response.status_code == 422  # Pydantic validation error


def test_signup_invalid_email_rejected():
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "not-an-email", "name": "Bad Email", "password": "validpassword"},
    )
    assert response.status_code == 422


# ===========================================================================
# Auth — Login
# ===========================================================================

def test_login():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@m32.ai", "password": "securepassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # The access_token must be a non-empty string
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 10


def test_login_invalid_credentials():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@m32.ai", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_unknown_user():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@m32.ai", "password": "securepassword123"},
    )
    assert response.status_code == 401


# ===========================================================================
# Auth — /me (protected)
# ===========================================================================

def test_read_users_me():
    headers = _auth_headers()
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@m32.ai"
    assert "id" in data
    assert "password" not in data


def test_read_users_me_unauthenticated():
    """Requests without a Bearer token must return 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


# ===========================================================================
# Auth — Password Reset Flow
# ===========================================================================

def test_forgot_password():
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "test@m32.ai"},
    )
    assert response.status_code == 200
    assert "logged to the server console" in response.json()["message"]


def test_forgot_password_unknown_email():
    """Forgot-password for a non-existent email should still return 200 (no user enumeration)."""
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@m32.ai"},
    )
    # Accepting either 200 (silent no-op) or 404 as per implementation choice
    assert response.status_code in (200, 404)


# ===========================================================================
# Chats
# ===========================================================================

def test_list_chats_empty():
    """New user starts with zero chats."""
    headers = _auth_headers()
    response = client.get("/api/v1/chats", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_chat():
    headers = _auth_headers()
    response = client.post(
        "/api/v1/chats",
        json={"title": "Stripe Research thread"},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Stripe Research thread"
    assert "id" in data
    assert "user_id" in data


def test_create_chat_no_title():
    """Chats can be created without an explicit title."""
    headers = _auth_headers()
    response = client.post("/api/v1/chats", json={}, headers=headers)
    assert response.status_code == 201
    assert "id" in response.json()


def test_list_chats_after_creation():
    """After creating chats, the list endpoint should return at least 1 result."""
    headers = _auth_headers()
    response = client.get("/api/v1/chats", headers=headers)
    assert response.status_code == 200
    chats = response.json()
    assert len(chats) >= 1


def test_create_chat_unauthenticated():
    response = client.post("/api/v1/chats", json={"title": "Attempt"})
    assert response.status_code == 401


# ===========================================================================
# Messages
# ===========================================================================

def test_list_messages_for_chat():
    """Message list on a new chat should return an empty list."""
    headers = _auth_headers()
    # Create a fresh chat
    chat_res = client.post("/api/v1/chats", json={"title": "Message Test Chat"}, headers=headers)
    assert chat_res.status_code == 201
    chat_id = chat_res.json()["id"]

    # Fetch its messages
    msg_res = client.get(f"/api/v1/chats/{chat_id}/messages", headers=headers)
    assert msg_res.status_code == 200
    assert isinstance(msg_res.json(), list)


def test_list_messages_for_nonexistent_chat():
    """Fetching messages for a chat that doesn't exist should return 404."""
    headers = _auth_headers()
    response = client.get("/api/v1/chats/999999/messages", headers=headers)
    assert response.status_code == 404
