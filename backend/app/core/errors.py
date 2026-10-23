"""Helpers for persisting and logging errors without leaking secrets."""

from __future__ import annotations


def exception_label(exc: BaseException) -> str:
    """Return a credential-safe error token for logs and agent_run.error."""
    return type(exc).__name__
