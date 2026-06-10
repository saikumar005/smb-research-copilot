from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.routes.auth import get_current_user
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatResponse
from app.repositories.chat_repository import ChatRepository

router = APIRouter()

@router.get("", response_model=List[ChatResponse])
def read_chats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all chat threads for the current logged-in user.
    """
    chat_repo = ChatRepository(db)
    return chat_repo.list_by_user_id(current_user.id)

@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_chat(
    chat_data: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new chat thread for the current logged-in user.
    """
    chat_repo = ChatRepository(db)
    return chat_repo.create(user_id=current_user.id, title=chat_data.title)

@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a specific chat thread. It must belong to the logged-in user.
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")
        
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this chat thread")
        
    chat_repo.delete(chat)
    return {"message": "Chat thread deleted successfully"}
