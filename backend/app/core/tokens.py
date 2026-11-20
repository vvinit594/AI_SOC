from __future__ import annotations

import hashlib
import hmac
import secrets


def new_urlsafe_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(provided: str, expected_hash: str) -> bool:
    provided_hash = hash_token(provided)
    return hmac.compare_digest(provided_hash, expected_hash)
