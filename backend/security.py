from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

PASSWORD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")


def hash_password(password: str) -> str:
    return PASSWORD_CONTEXT.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PASSWORD_CONTEXT.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return str(payload["sub"])


def _derive_fernet_key() -> bytes:
    if ENCRYPTION_KEY:
        key = ENCRYPTION_KEY.encode("utf-8")
        return key if len(key) == 44 else base64.urlsafe_b64encode(hashlib.sha256(key).digest())
    # Dev fallback only. Keep it deterministic locally.
    return base64.urlsafe_b64encode(hashlib.sha256(b"dev-encryption-key").digest())


def encrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    cipher = Fernet(_derive_fernet_key())
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str | None:
    if not value:
        return None
    cipher = Fernet(_derive_fernet_key())
    return cipher.decrypt(value.encode("utf-8")).decode("utf-8")


def safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
