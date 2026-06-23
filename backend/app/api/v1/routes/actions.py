from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.v1.routes.auth import get_current_user
from app.models.user import User
from app.schemas.action import ActionRequest, ActionValidateRequest, ActionValidateResponse
from app.schemas.message import MessageResponse
from app.repositories.chat_repository import ChatRepository
from app.repositories.message_repository import MessageRepository
from app.agents.graph import run_agent_workflow
from app.services.context_service import extract_chat_context

router = APIRouter()


@router.post(
    "/validate",
    response_model=ActionValidateResponse,
)
def validate_action_context(
    payload: ActionValidateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Guard-rail endpoint: scans the chat history to determine whether enough
    context exists to auto-execute the requested action mode.

    Returns:
      - can_execute=True  + auto_message  →  frontend should fire /actions/run immediately
      - can_execute=False + missing_fields →  frontend should ask only for what's missing
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(payload.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this thread")

    msg_repo = MessageRepository(db)
    db_messages = msg_repo.list_by_chat_id(payload.chat_id)

    # Build plain dicts for the context service
    formatted = [{"role": m.role, "content": m.content} for m in db_messages]

    result = extract_chat_context(messages=formatted, mode=payload.mode)

    return ActionValidateResponse(**result)


@router.post("/run", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def run_action(
    payload: ActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers a structured action (research, email_draft, task_list) in a chat thread.
    Invokes the multi-agent graph in that specific mode and saves the validated output.
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(payload.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to run actions in this thread")

    msg_repo = MessageRepository(db)

    # 1. Save user's instruction message with a mode-specific prefix
    mode_prefixes = {
        "research": "🔍 [Action: Research Company] ",
        "email_draft": "✉️ [Action: Draft Outreach Email] ",
        "task_list": "📋 [Action: Create Task Checklist] "
    }
    prefix = mode_prefixes.get(payload.mode, "")
    user_msg_content = f"{prefix}{payload.message}"
    user_msg = msg_repo.create(chat_id=payload.chat_id, role="user", content=user_msg_content)

    # 2. Load all past messages to feed to the graph for full context retention
    db_messages = msg_repo.list_by_chat_id(payload.chat_id)
    formatted_messages = [{"role": m.role, "content": m.content} for m in db_messages]

    # Auto-title chat thread if it is new
    if len(db_messages) <= 2:
        title_snippet = payload.message[:30] + "..." if len(payload.message) > 30 else payload.message
        chat_repo.update_title(chat, f"{payload.mode.upper()}: {title_snippet}")

    # 3. Invoke multi-agent graph with specific mode
    agent_output = run_agent_workflow(
        messages=formatted_messages,
        user_id=current_user.id,
        chat_id=payload.chat_id,
        mode=payload.mode
    )

    # Extract results
    final_text = agent_output.get("final_response", "[System Error: Action returned an empty response.]")
    findings = agent_output.get("research_findings", [])
    trace_id = agent_output.get("langfuse_trace_id")

    # Compile sources metadata for UI display
    metadata = {"action_mode": payload.mode}
    if findings:
        metadata["sources"] = [
            {"title": f["title"], "link": f["link"], "snippet": f["snippet"]}
            for f in findings
        ]
    if trace_id:
        metadata["langfuse_trace_id"] = trace_id

    # 4. Save the agent's output
    assistant_msg = msg_repo.create(
        chat_id=payload.chat_id,
        role="assistant",
        content=final_text,
        metadata_json=metadata
    )

    return assistant_msg


from fastapi.responses import StreamingResponse
import json
import asyncio
from app.agents.graph import run_agent_workflow_async

@router.post("/run/stream")
def run_action_stream(
    payload: ActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers a structured action (research, email_draft, task_list) in a chat thread,
    invokes multi-agent graph, and streams intermediate logs and tokens to the client.
    """
    chat_repo = ChatRepository(db)
    chat = chat_repo.get_by_id(payload.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat thread not found")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to run actions in this thread")

    msg_repo = MessageRepository(db)

    # 1. Save user's instruction message with a mode-specific prefix
    mode_prefixes = {
        "research": "🔍 [Action: Research Company] ",
        "email_draft": "✉️ [Action: Draft Outreach Email] ",
        "task_list": "📋 [Action: Create Task Checklist] "
    }
    prefix = mode_prefixes.get(payload.mode, "")
    user_msg_content = f"{prefix}{payload.message}"
    user_msg = msg_repo.create(chat_id=payload.chat_id, role="user", content=user_msg_content)

    # 2. Load all past messages to feed to the graph for context retention
    db_messages = msg_repo.list_by_chat_id(payload.chat_id)
    formatted_messages = [{"role": m.role, "content": m.content} for m in db_messages]

    # Auto-title chat thread if it is new
    if len(db_messages) <= 2:
        title_snippet = payload.message[:30] + "..." if len(payload.message) > 30 else payload.message
        chat_repo.update_title(chat, f"{payload.mode.upper()}: {title_snippet}")

    async def event_generator():
        queue = asyncio.Queue()
        
        # Start graph execution task in background
        task = asyncio.create_task(run_agent_workflow_async(
            messages=formatted_messages,
            user_id=current_user.id,
            chat_id=payload.chat_id,
            mode=payload.mode,
            event_queue=queue
        ))
        
        # Stream events from the queue while task is running or queue has pending items
        while not task.done() or not queue.empty():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.2)
                yield f"data: {json.dumps(event)}\n\n"
                queue.task_done()
            except asyncio.TimeoutError:
                continue
                
        # Wait for final execution state
        agent_output = await task
        final_text = agent_output.get("final_response", "[System Error: Action returned an empty response.]")
        findings = agent_output.get("research_findings", [])
        trace_id = agent_output.get("langfuse_trace_id")
        
        metadata = {"action_mode": payload.mode}
        if findings:
            metadata["sources"] = [
                {"title": f["title"], "link": f["link"], "snippet": f["snippet"]}
                for f in findings
            ]
        if trace_id:
            metadata["langfuse_trace_id"] = trace_id
            
        # 4. Save the agent's output to the database
        assistant_msg = msg_repo.create(
            chat_id=payload.chat_id,
            role="assistant",
            content=final_text,
            metadata_json=metadata
        )
        
        # Yield the final completion event
        final_event = {
            "type": "done",
            "message_id": assistant_msg.id,
            "content": final_text,
            "metadata_json": metadata
        }
        yield f"data: {json.dumps(final_event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

