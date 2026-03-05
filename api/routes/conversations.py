"""Conversation persistence — CRUD for AI chat history."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from api.auth import get_current_user
from api.db import get_engine, SCHEMA

logger = logging.getLogger("siteline")

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversation(BaseModel):
    title: str = "New chat"


class UpdateTitle(BaseModel):
    title: str


class SaveMessages(BaseModel):
    messages: list[dict]


@router.get("")
async def list_conversations(limit: int = 50, user: dict = Depends(get_current_user)):
    """List user's conversations, most recent first."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, title, created_at, updated_at
            FROM {SCHEMA}.conversations
            WHERE user_id = :uid
            ORDER BY updated_at DESC
            LIMIT :limit
        """), {"uid": user["id"], "limit": limit}).mappings().fetchall()
    return {"conversations": [dict(r) for r in rows]}


@router.post("")
async def create_conversation(req: CreateConversation, user: dict = Depends(get_current_user)):
    """Create a new conversation."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            INSERT INTO {SCHEMA}.conversations (user_id, title)
            VALUES (:uid, :title)
            RETURNING id, title, created_at, updated_at
        """), {"uid": user["id"], "title": req.title[:200]}).mappings().fetchone()
        conn.commit()
    return dict(row)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Load a conversation with all its messages."""
    engine = get_engine()
    with engine.connect() as conn:
        conv = conn.execute(text(f"""
            SELECT id, title, created_at, updated_at
            FROM {SCHEMA}.conversations
            WHERE id = :cid AND user_id = :uid
        """), {"cid": conversation_id, "uid": user["id"]}).mappings().fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")

        msgs = conn.execute(text(f"""
            SELECT id, role, content, tool_calls, created_at
            FROM {SCHEMA}.conversation_messages
            WHERE conversation_id = :cid
            ORDER BY created_at, id
        """), {"cid": conversation_id}).mappings().fetchall()

    result = dict(conv)
    result["messages"] = [dict(m) for m in msgs]
    return result


@router.patch("/{conversation_id}")
async def update_conversation(conversation_id: str, req: UpdateTitle, user: dict = Depends(get_current_user)):
    """Rename a conversation."""
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(f"""
            UPDATE {SCHEMA}.conversations
            SET title = :title, updated_at = NOW()
            WHERE id = :cid AND user_id = :uid
            RETURNING id, title, updated_at
        """), {"cid": conversation_id, "uid": user["id"], "title": req.title[:200]}).mappings().fetchone()
        conn.commit()
    if not row:
        raise HTTPException(404, "Conversation not found")
    return dict(row)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    """Delete a conversation and all its messages."""
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(f"""
            DELETE FROM {SCHEMA}.conversations
            WHERE id = :cid AND user_id = :uid
        """), {"cid": conversation_id, "uid": user["id"]})
        conn.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "Conversation not found")
    return {"ok": True}


@router.post("/{conversation_id}/messages")
async def save_messages(conversation_id: str, req: SaveMessages, user: dict = Depends(get_current_user)):
    """Batch-save messages to a conversation."""
    engine = get_engine()
    with engine.connect() as conn:
        # Verify ownership
        conv = conn.execute(text(f"""
            SELECT id FROM {SCHEMA}.conversations
            WHERE id = :cid AND user_id = :uid
        """), {"cid": conversation_id, "uid": user["id"]}).fetchone()
        if not conv:
            raise HTTPException(404, "Conversation not found")

        for msg in req.messages:
            tool_calls = msg.get("tool_calls") or msg.get("toolCalls")
            conn.execute(text(f"""
                INSERT INTO {SCHEMA}.conversation_messages (conversation_id, role, content, tool_calls)
                VALUES (:cid, :role, :content, :tc)
            """), {
                "cid": conversation_id,
                "role": msg["role"],
                "content": msg.get("content", ""),
                "tc": json.dumps(tool_calls) if tool_calls else None,
            })

        conn.execute(text(f"""
            UPDATE {SCHEMA}.conversations SET updated_at = NOW() WHERE id = :cid
        """), {"cid": conversation_id})
        conn.commit()

    return {"saved": len(req.messages)}
