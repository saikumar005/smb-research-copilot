from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.routes.auth import get_current_user
from app.models.user import User
from app.schemas.message import MessageCreate, MessageResponse
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.agents.graph import run_agent_workflow

router = APIRouter()

@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
def get_chat_messages(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve message history for a specific chat thread.
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")
        
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view messages in this thread")
        
    msg_repo = MessageRepository(db)
    return msg_repo.list_by_chat_id(chat_id)

@router.post("/chats/{chat_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def post_chat_message(
    chat_id: int,
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Post a new user message to a chat thread, triggers the multi-agent workflow, 
    persists the agent's output, and returns the response message.
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")
        
    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to message in this thread")
        
    msg_repo = MessageRepository(db)
    
    # 1. Save user's input message
    user_msg = msg_repo.create(chat_id=chat_id, role="user", content=payload.content)
    
    # 2. Load all past messages to pass to the agent graph for session context
    db_messages = msg_repo.list_by_chat_id(chat_id)
    formatted_messages = []
    for m in db_messages:
        formatted_messages.append({
            "role": m.role,
            "content": m.content
        })
        
    # If the first message in the chat is created, auto-update the title of the chat thread based on user's query
    if len(db_messages) <= 2:
        title_snippet = payload.content[:30] + "..." if len(payload.content) > 30 else payload.content
        chat_repo.update_title(chat, title_snippet)
        
    # 3. Invoke the LangGraph Multi-Agent Workflow
    agent_output = run_agent_workflow(
        messages=formatted_messages,
        user_id=current_user.id,
        chat_id=chat_id,
        mode="general"
    )
    
    # Extract outcomes
    final_text = agent_output.get("final_response", "[System Error: Agent response was empty.]")
    findings = agent_output.get("research_findings", [])
    
    # Build structured metadata (stores links and query traces for the UI)
    metadata = {}
    if findings:
        metadata["sources"] = [
            {"title": f["title"], "link": f["link"], "snippet": f["snippet"]}
            for f in findings
        ]
        
    # 4. Save the agent's final generated output
    assistant_msg = msg_repo.create(
        chat_id=chat_id,
        role="assistant",
        content=final_text,
        metadata_json=metadata
    )
    
    return assistant_msg
