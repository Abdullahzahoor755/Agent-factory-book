from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class DocumentChunk:
    text: str
    source: str
    chapter: str
    chunk_index: int


def load_markdown(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def extract_chapter_name(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return fallback


def chunk_text(text: str, chunk_size: int = 1400, overlap: int = 200) -> list[str]:
    cleaned = " ".join(text.split())
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def load_knowledge_base(kb_dir: str | Path, chunk_size: int = 1400, overlap: int = 200) -> list[DocumentChunk]:
    kb_path = Path(kb_dir)
    chunks: list[DocumentChunk] = []
    for md_path in sorted(kb_path.glob("*.md")):
        text = load_markdown(md_path)
        chapter = extract_chapter_name(text, md_path.stem)
        for i, chunk in enumerate(chunk_text(text, chunk_size=chunk_size, overlap=overlap)):
            chunks.append(
                DocumentChunk(
                    text=chunk,
                    source=md_path.name,
                    chapter=chapter,
                    chunk_index=i,
                )
            )
    return chunks
