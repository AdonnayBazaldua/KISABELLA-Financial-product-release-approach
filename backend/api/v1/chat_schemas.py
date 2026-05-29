# backend/api/v1/chat_schemas.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageCreated(BaseModel):
    message_id: UUID
    status: str = "streaming"


class AttachmentDTO(BaseModel):
    id: UUID
    original_name: str
    mime_type: str
    size_bytes: int

    model_config = {"from_attributes": True}


class ChatMessageDTO(BaseModel):
    id: UUID
    role: str
    content: str
    status: str
    error_msg: str | None = None
    created_at: datetime
    attachments: list[AttachmentDTO] = Field(default_factory=list)

    model_config = {"from_attributes": True}
