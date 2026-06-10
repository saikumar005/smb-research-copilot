from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class MessageBase(BaseModel):
    role: str
    content: str
    metadata_json: Optional[Dict[str, Any]] = None

class MessageCreate(BaseModel):
    content: str

class MessageResponse(MessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chat_id: int
    created_at: datetime
