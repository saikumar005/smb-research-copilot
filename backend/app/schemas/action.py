from pydantic import BaseModel, Field
from typing import Literal, Optional, List


class ActionRequest(BaseModel):
    chat_id: int
    mode: Literal["research", "email_draft", "task_list"]
    message: str = Field(..., description="The context or instruction for the action")


class ActionValidateRequest(BaseModel):
    chat_id: int
    mode: Literal["research", "email_draft", "task_list"]


class ActionValidateResponse(BaseModel):
    """
    Returned by POST /actions/validate.
    Tells the frontend whether it has enough context to auto-execute the action,
    or which required fields are still missing.
    """
    can_execute: bool = Field(
        description="True if the chat already contains all required context to run the action."
    )
    company_name: Optional[str] = Field(
        default=None,
        description="Company name extracted from chat history, if found."
    )
    context_summary: Optional[str] = Field(
        default=None,
        description="One-line summary of what context was found (for logging/debugging)."
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="List of required fields not found in the chat history."
    )
    auto_message: Optional[str] = Field(
        default=None,
        description="If can_execute is True, the pre-built message to pass to /actions/run."
    )
