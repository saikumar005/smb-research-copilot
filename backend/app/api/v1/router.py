from fastapi import APIRouter
from app.api.v1.routes import auth, chats, messages, memory, actions

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(messages.router, tags=["messages"])  # Has internal /chats/{chat_id}/messages paths
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(actions.router, prefix="/actions", tags=["actions"])
