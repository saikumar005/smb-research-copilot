from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.chat import Chat

class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, chat_id: int) -> Optional[Chat]:
        return self.db.query(Chat).filter(Chat.id == chat_id).first()

    def list_by_user_id(self, user_id: int) -> List[Chat]:
        # Return chats sorted by updated_at descending so newest are on top
        return self.db.query(Chat).filter(Chat.user_id == user_id).order_by(Chat.updated_at.desc()).all()

    def create(self, user_id: int, title: Optional[str] = None) -> Chat:
        chat = Chat(
            user_id=user_id,
            title=title or "New Research Thread"
        )
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def update_title(self, chat: Chat, title: str) -> Chat:
        chat.title = title
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def update_summary(self, chat: Chat, summary: str) -> Chat:
        chat.summary = summary
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def delete(self, chat: Chat) -> None:
        self.db.delete(chat)
        self.db.commit()
