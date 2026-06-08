from __future__ import annotations

from pathlib import Path

import chromadb

from config import CHROMA_COLLECTION, VECTOR_DB_DIR


class VectorStore:
    def __init__(self, path: str | Path = VECTOR_DB_DIR, collection_name: str = CHROMA_COLLECTION):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.path))
        self.collection = self.client.get_or_create_collection(collection_name)

    def reset(self) -> None:
        try:
            self.client.delete_collection(self.collection.name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(self.collection.name)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict], embeddings: list[list[float]]) -> None:
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    def search(self, query_embedding: list[float], limit: int = 5, where: dict | None = None):
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
