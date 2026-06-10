from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserRegister(UserBase):
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    google_id: Optional[str] = None
    # Indicates how the user authenticated in this session
    auth_provider: Optional[Literal["email", "google"]] = None
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Indicates which auth provider issued this token
    auth_provider: Literal["email", "google"] = "email"


class TokenData(BaseModel):
    user_id: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


class GoogleAuthRequest(BaseModel):
    """Payload from the Google Identity Services popup flow."""
    id_token: str = Field(..., description="Google ID token from GIS credential response")

