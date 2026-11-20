"""Argon2id password hashing. Never log or return hashes to clients."""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# OWASP-recommended Argon2id parameters (m=19456 KiB, t=2, p=1).
_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16)
_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")


class PasswordPolicyError(ValueError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def validate_password(password: str, *, email: str | None = None) -> None:
    if len(password) < 12:
        raise PasswordPolicyError("Password must be at least 12 characters")
    if len(password) > 128:
        raise PasswordPolicyError("Password must be at most 128 characters")
    if _HAS_LETTER.search(password) is None or _HAS_DIGIT.search(password) is None:
        raise PasswordPolicyError("Password must include letters and numbers")
    if email and password.lower() == email.lower():
        raise PasswordPolicyError("Password must not match the email address")


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError, TypeError):
        return False


def burn_verify_time() -> None:
    """Hash a dummy secret so missing-user logins take similar time."""
    _HASHER.hash("aisoc-missing-user-dummy")
