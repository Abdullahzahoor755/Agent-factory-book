from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
KB_DIR = BASE_DIR / "knowledge_base"
VECTOR_DB_DIR = BASE_DIR / "vector_db"

load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "agent_factory_book")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
TOP_K = int(os.getenv("TOP_K", "5"))
