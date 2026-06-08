from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import requests
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config import CHUNK_OVERLAP, CHUNK_SIZE, FRONTEND_DIR, KB_DIR, VECTOR_DB_DIR
from database import Base, engine, get_db
from embeddings import embed_texts
from loaders import load_knowledge_base
from models import AgentRun, ApiConnection, ApiTool, User
from rag_agent import NO_INFO_MESSAGE, RAGAgent
from schemas import (
    AgentChatRequest,
    ConnectionCreate,
    ConnectionOut,
    LoginRequest,
    SignupRequest,
    TokenResponse,
    ToolCreate,
    ToolOut,
    ToolTestRequest,
    UserOut,
)
from security import (
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    safe_compare,
    verify_password,
    decode_access_token,
)
from vector_store import VectorStore


RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 20
_rate_limit_bucket: dict[str, list[float]] = {}


def check_rate_limit(key: str) -> None:
    now = time.time()
    timestamps = [stamp for stamp in _rate_limit_bucket.get(key, []) if now - stamp < RATE_LIMIT_WINDOW_SECONDS]
    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please slow down.")
    timestamps.append(now)
    _rate_limit_bucket[key] = timestamps


def oauth_user_from_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def current_user(authorization: str | None = Header(default=None), db=Depends(get_db)) -> User:
    email = oauth_user_from_token(authorization)
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def user_scope(db, user_id: int):
    return (
        db.query(ApiConnection)
        .filter(ApiConnection.user_id == user_id)
    )


def serialize_connection(connection: ApiConnection) -> dict[str, Any]:
    return {
        "id": connection.id,
        "provider_name": connection.provider_name,
        "auth_type": connection.auth_type,
        "base_url": connection.base_url,
        "default_headers": connection.default_headers or {},
        "created_at": connection.created_at,
    }


def serialize_tool(tool: ApiTool) -> dict[str, Any]:
    return {
        "id": tool.id,
        "connection_id": tool.connection_id,
        "tool_name": tool.tool_name,
        "description": tool.description,
        "method": tool.method,
        "endpoint": tool.endpoint,
        "request_schema": tool.request_schema or {},
        "response_schema": tool.response_schema or {},
        "safety_level": tool.safety_level,
        "created_at": tool.created_at,
    }


def normalize_method(method: str) -> str:
    return method.strip().upper()


def build_headers(connection: ApiConnection, auth_secret: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if connection.default_headers:
        headers.update({str(k): str(v) for k, v in connection.default_headers.items()})
    secret = auth_secret or decrypt_secret(connection.encrypted_secret)
    if connection.auth_type == "api_key" and secret:
        headers.setdefault("X-API-Key", secret)
    elif connection.auth_type == "bearer_token" and secret:
        headers.setdefault("Authorization", f"Bearer {secret}")
    return headers


def call_external_api(tool: ApiTool, connection: ApiConnection, payload: dict | None = None) -> dict[str, Any]:
    base_url = connection.base_url.rstrip("/")
    endpoint = tool.endpoint if tool.endpoint.startswith("http") else f"{base_url}/{tool.endpoint.lstrip('/')}"
    timeout_seconds = 15
    headers = build_headers(connection)
    method = normalize_method(tool.method)
    response = requests.request(method, endpoint, json=payload or {}, headers=headers, timeout=timeout_seconds)
    data: Any
    try:
        data = response.json()
    except Exception:
        data = response.text
    return {
        "status_code": response.status_code,
        "ok": response.ok,
        "data": data,
    }


def tool_matches_question(question: str, tool: ApiTool) -> int:
    question_terms = set(question.lower().split())
    desc = f"{tool.tool_name} {tool.description} {tool.endpoint}".lower()
    score = sum(1 for word in question_terms if word in desc)
    if tool.tool_name.lower() in question.lower():
        score += 5
    return score


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Agent Factory Book API", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

vector_store = VectorStore(VECTOR_DB_DIR)
rag_agent = RAGAgent(vector_store)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "frontend_dir": str(FRONTEND_DIR),
        "vector_db_dir": str(VECTOR_DB_DIR),
    }


@app.post("/ingest")
def ingest():
    chunks = load_knowledge_base(KB_DIR, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise HTTPException(status_code=400, detail="No markdown files found in knowledge_base/")

    vector_store.reset()
    texts = [chunk.text for chunk in chunks]
    embeddings = embed_texts(texts)
    ids = [f"{chunk.source}-{chunk.chunk_index}" for chunk in chunks]
    metadatas = [
        {"source": chunk.source, "chapter": chunk.chapter, "chunk_index": chunk.chunk_index}
        for chunk in chunks
    ]
    vector_store.add(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)
    chapters = sorted(set(chunk.chapter for chunk in chunks))
    return {"status": "ok", "chunks": len(chunks), "chapters": chapters}


@app.post("/auth/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email.lower().strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.email))


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db=Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.email))


@app.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active)


@app.post("/connections", response_model=ConnectionOut)
def create_connection(payload: ConnectionCreate, user: User = Depends(current_user), db=Depends(get_db)):
    connection = ApiConnection(
        user_id=user.id,
        provider_name=payload.provider_name,
        auth_type=payload.auth_type,
        base_url=payload.base_url,
        encrypted_secret=encrypt_secret(payload.api_key_or_token),
        default_headers=payload.default_headers or {},
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return serialize_connection(connection)


@app.get("/connections")
def list_connections(user: User = Depends(current_user), db=Depends(get_db)):
    connections = db.scalars(select(ApiConnection).where(ApiConnection.user_id == user.id)).all()
    return [serialize_connection(connection) for connection in connections]


@app.delete("/connections/{connection_id}")
def delete_connection(connection_id: int, user: User = Depends(current_user), db=Depends(get_db)):
    connection = db.scalar(
        select(ApiConnection).where(ApiConnection.id == connection_id, ApiConnection.user_id == user.id)
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    db.delete(connection)
    db.commit()
    return {"status": "deleted"}


@app.post("/connections/{connection_id}/test")
def test_connection(connection_id: int, user: User = Depends(current_user), db=Depends(get_db)):
    connection = db.scalar(
        select(ApiConnection).where(ApiConnection.id == connection_id, ApiConnection.user_id == user.id)
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        response = requests.get(connection.base_url, headers=build_headers(connection), timeout=10)
        return {"status": "ok", "status_code": response.status_code}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection test failed: {exc}") from exc


@app.post("/tools", response_model=ToolOut)
def create_tool(payload: ToolCreate, user: User = Depends(current_user), db=Depends(get_db)):
    connection = db.scalar(
        select(ApiConnection).where(ApiConnection.id == payload.connection_id, ApiConnection.user_id == user.id)
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    tool = ApiTool(
        user_id=user.id,
        connection_id=connection.id,
        tool_name=payload.tool_name,
        description=payload.description,
        method=normalize_method(payload.method),
        endpoint=payload.endpoint,
        request_schema=payload.request_schema or {},
        response_schema=payload.response_schema or {},
        safety_level=payload.safety_level,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return serialize_tool(tool)


@app.get("/tools")
def list_tools(user: User = Depends(current_user), db=Depends(get_db)):
    tools = db.scalars(select(ApiTool).where(ApiTool.user_id == user.id)).all()
    return [serialize_tool(tool) for tool in tools]


@app.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, user: User = Depends(current_user), db=Depends(get_db)):
    tool = db.scalar(select(ApiTool).where(ApiTool.id == tool_id, ApiTool.user_id == user.id))
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    db.delete(tool)
    db.commit()
    return {"status": "deleted"}


@app.post("/tools/{tool_id}/test")
def test_tool(tool_id: int, payload: ToolTestRequest | None = None, user: User = Depends(current_user), db=Depends(get_db)):
    tool = db.scalar(select(ApiTool).where(ApiTool.id == tool_id, ApiTool.user_id == user.id))
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    connection = db.scalar(select(ApiConnection).where(ApiConnection.id == tool.connection_id, ApiConnection.user_id == user.id))
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        result = call_external_api(tool, connection, payload.payload if payload else None)
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Tool test failed: {exc}") from exc


def choose_tool(question: str, tools: list[ApiTool], tool_hint: str | None = None) -> ApiTool | None:
    if tool_hint:
        for tool in tools:
            if tool_hint.lower() in tool.tool_name.lower() or tool_hint.lower() in tool.description.lower():
                return tool
    ranked = sorted(tools, key=lambda tool: tool_matches_question(question, tool), reverse=True)
    return ranked[0] if ranked and tool_matches_question(question, ranked[0]) > 0 else None


def summarize_tool_result(tool: ApiTool, result: dict[str, Any], mode: str) -> str:
    if not result.get("ok"):
        return f"Tool call failed with status {result.get('status_code')}. Related tool: {tool.tool_name}"
    data = result.get("data")
    if mode == "summarize":
        return f"Tool `{tool.tool_name}` succeeded. Summary: {str(data)[:700]}"
    if mode == "explain_simple":
        return f"Simple explanation: tool `{tool.tool_name}` ne API se data le liya. Result: {str(data)[:700]}"
    if mode == "quiz":
        return f"Quiz style: ` {tool.tool_name}` tool ne kya return kiya? Answer: {str(data)[:700]}"
    if mode == "practical_task":
        return f"Practical task result from `{tool.tool_name}`: {str(data)[:700]}"
    if mode == "interview_prep":
        return f"Interview prep: `{tool.tool_name}` API call successful. Key result: {str(data)[:700]}"
    return f"Tool `{tool.tool_name}` response: {str(data)[:1000]}"


@app.post("/chat")
def chat(request: AgentChatRequest, authorization: str | None = Header(default=None), db=Depends(get_db)):
    user_email = oauth_user_from_token(authorization)
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    check_rate_limit(f"user:{user.id}")

    user_tools = db.scalars(select(ApiTool).where(ApiTool.user_id == user.id)).all()
    selected_tool = choose_tool(request.question, user_tools, request.tool_hint)
    run = AgentRun(
        user_id=user.id,
        question=request.question,
        mode=request.mode,
        selected_tool_id=selected_tool.id if selected_tool else None,
        status="started",
        input_payload={"chapter": request.chapter, "confirm": request.confirm, "tool_hint": request.tool_hint},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    if selected_tool:
        connection = db.scalar(
            select(ApiConnection).where(
                ApiConnection.id == selected_tool.connection_id,
                ApiConnection.user_id == user.id,
            )
        )
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        if selected_tool.safety_level in {"write", "delete"} and not request.confirm:
            run.status = "confirmation_required"
            run.output_payload = {
                "message": f"Tool `{selected_tool.tool_name}` is {selected_tool.safety_level}. Please confirm to proceed.",
                "tool_id": selected_tool.id,
            }
            db.commit()
            return {
                "answer": f"Tool `{selected_tool.tool_name}` needs confirmation before calling.",
                "requires_confirmation": True,
                "selected_tool": serialize_tool(selected_tool),
                "sources": [],
                "matched_chapters": [],
            }

        try:
            api_result = call_external_api(selected_tool, connection, payload={"question": request.question})
            summary = summarize_tool_result(selected_tool, api_result, request.mode)
            run.status = "completed"
            run.output_payload = {"tool_result": api_result}
            db.commit()
            return {
                "answer": summary,
                "sources": [
                    {
                        "source": f"api:{connection.provider_name}",
                        "chapter": "User API Tool",
                        "chunk_index": 0,
                    }
                ],
                "matched_chapters": ["User API Tool"],
                "selected_tool": serialize_tool(selected_tool),
            }
        except Exception as exc:
            run.status = "failed"
            run.output_payload = {"error": str(exc)}
            db.commit()
            raise HTTPException(status_code=400, detail=f"Tool call failed: {exc}") from exc

    rag_result = rag_agent.chat(question=request.question, mode=request.mode, chapter=request.chapter)
    run.status = "completed"
    run.output_payload = {"answer": rag_result.answer, "sources": rag_result.sources}
    db.commit()
    return {
        "answer": rag_result.answer,
        "sources": rag_result.sources,
        "matched_chapters": rag_result.matched_chapters,
        "selected_tool": None,
    }
