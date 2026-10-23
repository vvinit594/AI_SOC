from __future__ import annotations

import json
import logging
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import exception_label

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when an LLM call fails or returns invalid structured output."""


class LLMClient(Protocol):
    def generate(self, *, system: str, user: str, schema: type[T]) -> T: ...


class UnavailableLLM:
    def generate(self, *, system: str, user: str, schema: type[T]) -> T:
        raise LLMError("LLM provider is disabled or unconfigured")


class OpenAICompatibleLLM:
    def __init__(self, api_key: str, model: str, timeout_seconds: int, max_retries: int) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    def generate(self, *, system: str, user: str, schema: type[T]) -> T:
        last_error: Exception | None = None
        payload = {
            "model": self._model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        attempts = self._max_retries + 1
        for _ in range(attempts):
            try:
                response = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return schema.model_validate(json.loads(content))
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                ValidationError,
            ) as exc:
                last_error = exc
                logger.warning("LLM structured output failed: %s", exception_label(exc))
        raise LLMError(
            "LLM structured output invalid or unavailable: "
            f"{exception_label(last_error) if last_error else 'Error'}"
        ) from last_error


def build_llm_client(settings: Settings, override: LLMClient | None = None) -> LLMClient:
    if override is not None:
        return override
    if settings.llm_provider == "openai" and settings.llm_api_key:
        return OpenAICompatibleLLM(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
    return UnavailableLLM()
