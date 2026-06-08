from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import re

from config import OPENAI_API_KEY, OPENAI_MODEL, TOP_K
from embeddings import embed_texts
from vector_store import VectorStore


NO_INFO_MESSAGE = "The current book content does not contain enough information about this."


@dataclass
class ChatResult:
    answer: str
    sources: list[dict[str, Any]]
    matched_chapters: list[str]


class RAGAgent:
    def __init__(self, store: VectorStore | None = None):
        self.store = store or VectorStore()

    def _build_context(self, hits: dict) -> tuple[str, list[dict[str, Any]], list[str]]:
        documents = hits.get("documents", [[]])[0]
        metadatas = hits.get("metadatas", [[]])[0]
        sources: list[dict[str, Any]] = []
        matched_chapters: list[str] = []
        lines: list[str] = []
        for doc, meta in zip(documents, metadatas):
            source = {
                "source": meta.get("source", "unknown"),
                "chapter": meta.get("chapter", "unknown"),
                "chunk_index": meta.get("chunk_index", 0),
            }
            sources.append(source)
            matched_chapters.append(source["chapter"])
            lines.append(f"[{source['chapter']} | {source['source']} | chunk {source['chunk_index']}]\n{doc}")
        return "\n\n".join(lines), sources, sorted(set(matched_chapters))

    def _answer_with_openai(self, question: str, context: str, mode: str) -> str:
        if not OPENAI_API_KEY:
            return ""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY)
            system = (
                "You are a friendly AI tutor. Answer only from the provided book context. "
                f"If the answer is missing, reply exactly: {NO_INFO_MESSAGE}. "
                "Use simple Roman Urdu with easy English, examples, and always mention related chapter/source."
            )
            if mode == "summarize":
                extra = "Give a concise summary."
            elif mode == "explain_simple":
                extra = "Explain in very simple beginner-friendly language."
            elif mode == "quiz":
                extra = "Turn the answer into short quiz style with one or two questions."
            elif mode == "practical_task":
                extra = "Provide a practical task or exercise."
            elif mode == "interview_prep":
                extra = "Prepare interview-style talking points."
            else:
                extra = "Answer clearly and helpfully."
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": f"Mode: {mode}\nInstruction: {extra}\n\nBook context:\n{context}\n\nQuestion: {question}"},
                ],
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""

    def _extractive_answer(self, question: str, context: str) -> str:
        question_terms = {term for term in re.findall(r"[a-z0-9]+", question.lower()) if len(term) > 2}
        if not question_terms:
            return NO_INFO_MESSAGE

        best_lines: list[str] = []
        best_score = 0
        for paragraph in context.split("\n\n"):
            paragraph_terms = set(re.findall(r"[a-z0-9]+", paragraph.lower()))
            score = len(question_terms & paragraph_terms)
            if score > best_score:
                best_score = score
                best_lines = [paragraph]

        if best_score == 0:
            return NO_INFO_MESSAGE

        return "\n\n".join(best_lines)

    def chat(self, question: str, mode: str = "normal", chapter: str | None = None) -> ChatResult:
        query_embedding = embed_texts([question])[0]
        where = {"chapter": chapter} if chapter else None
        hits = self.store.search(query_embedding, limit=TOP_K, where=where)
        context, sources, matched_chapters = self._build_context(hits)

        if not context.strip():
            return ChatResult(answer=NO_INFO_MESSAGE, sources=[], matched_chapters=[])

        answer = self._answer_with_openai(question, context, mode)
        if not answer:
            answer = self._extractive_answer(question, context)

        if NO_INFO_MESSAGE.lower() in answer.lower():
            return ChatResult(answer=NO_INFO_MESSAGE, sources=sources[:TOP_K], matched_chapters=matched_chapters)

        if "related chapter/source" not in answer.lower() and sources:
            answer = f"{answer}\n\nRelated chapter/source: {sources[0]['chapter']} / {sources[0]['source']}"
        return ChatResult(answer=answer, sources=sources[:TOP_K], matched_chapters=matched_chapters)
