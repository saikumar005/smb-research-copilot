from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.routes.auth import get_current_user
from app.models.user import User
from app.schemas.memory import MemoryResponse
from app.services.memory_service import MemoryService

router = APIRouter()

@router.get("", response_model=List[MemoryResponse])
def get_memories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all long-term facts and preferences remembered by the AI for the logged-in user.
    """
    return MemoryService.get_user_memories(db, current_user.id)

@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific fact or preference from the AI's memory.
    """
    success = MemoryService.delete_user_memory(db, memory_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete memory. Memory may not exist or belong to another user."
        )
    return {"message": "Memory deleted successfully."}
