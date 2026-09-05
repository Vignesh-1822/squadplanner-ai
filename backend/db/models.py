"""Pydantic models for persisted documents."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class InvitedMemberDocument(BaseModel):
    email: str
    status: Literal["pending", "accepted", "declined"] = "pending"


class TripDocument(BaseModel):
    id: str | None = Field(None, alias="_id")
    status: str = "pending"
    state: dict[str, Any] = Field(default_factory=dict)
    invited_members: list[InvitedMemberDocument] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class UserDocument(BaseModel):
    id: str | None = Field(None, alias="_id")
    email: str
    name: str
    avatar_url: str = ""
    auth_provider: Literal["local", "google"] = "local"
    hashed_password: str | None = None
    created_at: str = ""
    token_version: int = 0
    is_admin: bool = False

    model_config = {"populate_by_name": True}
