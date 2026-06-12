from pydantic import BaseModel, EmailStr
from typing import Optional


class GmailSendRequest(BaseModel):
    """Payload for POST /integrations/gmail/send"""
    to: EmailStr
    subject: str
    body: str
    cc: Optional[str] = None


class GmailStatusResponse(BaseModel):
    connected: bool


class GmailConnectResponse(BaseModel):
    redirect_url: str


class GmailSendResponse(BaseModel):
    success: bool
    message: str = ""
