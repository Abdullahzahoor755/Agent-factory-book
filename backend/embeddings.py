from __future__ import annotations

import math
import re
from collections import Counter
from hashlib import sha256

from config import EMBEDDING_MODEL, OPENAI_API_KEY


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _hash_embedding(text: str, dimensions: int = 384) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokenize(text)
    counts = Counter(tokens)
    if not counts:
        return vector
    for token, weight in counts.items():
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * float(weight)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if OPENAI_API_KEY:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data]
        except Exception:
            pass
    return [_hash_embedding(text) for text in texts]
