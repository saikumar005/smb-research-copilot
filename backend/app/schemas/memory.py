from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Any
    entity_id: str
    content: str
    created_at: Optional[Any] = None
