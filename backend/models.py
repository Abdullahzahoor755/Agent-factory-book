from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    connections = relationship("ApiConnection", back_populates="user", cascade="all, delete-orphan")
    tools = relationship("ApiTool", back_populates="user", cascade="all, delete-orphan")
    runs = relationship("AgentRun", back_populates="user", cascade="all, delete-orphan")


class ApiConnection(Base):
    __tablename__ = "api_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    encrypted_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="connections")
    tools = relationship("ApiTool", back_populates="connection", cascade="all, delete-orphan")


class ApiTool(Base):
    __tablename__ = "api_tools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    connection_id: Mapped[int] = mapped_column(ForeignKey("api_connections.id"), index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False)
    request_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safety_level: Mapped[str] = mapped_column(String(20), nullable=False, default="read")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tools")
    connection = relationship("ApiConnection", back_populates="tools")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)
    selected_tool_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="completed")
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="runs")
