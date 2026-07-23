from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.agents.chat_graph import chat_graph

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatResponse)
def send_message(payload: schemas.ChatRequest, db: Session = Depends(get_db)):
    # Persist the incoming user message
    user_msg = models.ChatMessage(
        session_id=payload.session_id,
        complaint_id=payload.complaint_id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    db.commit()

    # Pull prior history for this session so the assistant has conversational memory
    history_rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == payload.session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in history_rows]

    result = chat_graph.invoke({"history": history, "context": payload.context or {}})
    reply = result.get("reply", "Sorry, I couldn't process that.")

    assistant_msg = models.ChatMessage(
        session_id=payload.session_id,
        complaint_id=payload.complaint_id,
        role="assistant",
        content=reply,
    )
    db.add(assistant_msg)
    db.commit()

    history_rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == payload.session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    return schemas.ChatResponse(
        reply=reply,
        history=[schemas.ChatMessageOut.model_validate(m) for m in history_rows],
    )


@router.get("/{session_id}/history", response_model=List[schemas.ChatMessageOut])
def get_history(session_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )
    return rows
