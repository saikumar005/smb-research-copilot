from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.message import Message

class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_by_chat_id(self, chat_id: int) -> List[Message]:
        return self.db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at.asc()).all()

    def create(self, chat_id: int, role: str, content: str, metadata_json: Optional[Dict[str, Any]] = None) -> Message:
        message = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            metadata_json=metadata_json
        )
        self.db.add(message)
        
        # Touch the parent chat's updated_at timestamp so it floats to the top of list
        from app.models.chat import Chat
        chat = self.db.query(Chat).filter(Chat.id == chat_id).first()
        if chat:
            from datetime import datetime, timezone
            chat.updated_at = datetime.now(timezone.utc)
            self.db.add(chat)
            
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_by_id(self, message_id: int) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == message_id).first()

    def update_metadata(self, message: Message, metadata_json: Optional[Dict[str, Any]]) -> Message:
        message.metadata_json = metadata_json
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message
