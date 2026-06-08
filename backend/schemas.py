from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool


class ConnectionCreate(BaseModel):
    provider_name: str
    auth_type: str
    base_url: str
    api_key_or_token: str | None = None
    default_headers: dict | None = None


class ConnectionOut(BaseModel):
    id: int
    provider_name: str
    auth_type: str
    base_url: str
    default_headers: dict | None = None
    created_at: datetime


class ToolCreate(BaseModel):
    connection_id: int
    tool_name: str
    description: str
    method: str
    endpoint: str
    request_schema: dict | None = None
    response_schema: dict | None = None
    safety_level: str = "read"


class ToolOut(BaseModel):
    id: int
    connection_id: int
    tool_name: str
    description: str
    method: str
    endpoint: str
    request_schema: dict | None = None
    response_schema: dict | None = None
    safety_level: str
    created_at: datetime


class ToolTestRequest(BaseModel):
    payload: dict | None = None


class AgentChatRequest(BaseModel):
    question: str = Field(min_length=1)
    mode: str = "normal"
    chapter: str | None = None
    tool_hint: str | None = None
    confirm: bool = False

