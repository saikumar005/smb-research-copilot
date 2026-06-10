from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ChatBase(BaseModel):
    title: Optional[str] = None

class ChatCreate(ChatBase):
    pass

class ChatResponse(ChatBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
