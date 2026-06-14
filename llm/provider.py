from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Base exception for provider-level failures."""


class LLMResponseFormatError(LLMProviderError):
    """Raised when the model response is not valid structured analysis JSON."""


class LLMContextWindowError(LLMProviderError):
    """Raised when the prompt payload exceeds the model context window."""


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider asks callers to retry later."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(slots=True, frozen=True)
class AnnouncementPageImage:
    """Image payload for a single announcement page."""

    page_number: int
    mime_type: str
    data_base64: str


@dataclass(slots=True, frozen=True)
class AnnouncementAnalysis:
    """Normalized analysis returned by an LLM provider."""

    summary: str
    category: str
    confidence: str
    need_more_pages: bool | None = None


_VALID_CONFIDENCE = {"high", "medium", "low"}


def parse_analysis_json(
    raw_output: str, *, categories: Sequence[str] | None = None
) -> AnnouncementAnalysis:
    """Parse and validate structured announcement analysis JSON."""
    parsed = _load_json_object(raw_output)

    summary = _require_non_empty_str(parsed, "summary")
    category = _require_non_empty_str(parsed, "category")
    confidence = _require_confidence(parsed, "confidence")
    need_more_pages = _require_optional_need_more_pages(parsed.get("need_more_pages"))

    if categories and category not in categories:
        raise LLMResponseFormatError(
            f"Unknown category {category!r}. Expected one of: {', '.join(categories)}"
        )

    return AnnouncementAnalysis(
        summary=summary,
        category=category,
        confidence=confidence,
        need_more_pages=need_more_pages,
    )


def _load_json_object(raw_output: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise LLMResponseFormatError("Model output is not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise LLMResponseFormatError("Model output JSON must be an object.")
    return parsed


def _require_non_empty_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LLMResponseFormatError(f"Field {key!r} must be a non-empty string.")
    return value.strip()


def _require_confidence(payload: dict[str, Any], key: str) -> str:
    confidence = _require_non_empty_str(payload, key).lower()
    if confidence not in _VALID_CONFIDENCE:
        raise LLMResponseFormatError(
            f"Field 'confidence' must be one of: {', '.join(sorted(_VALID_CONFIDENCE))}."
        )
    return confidence


def _require_optional_need_more_pages(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    raise LLMResponseFormatError("Field 'need_more_pages' must be a boolean or null.")


@runtime_checkable
class LLMProvider(Protocol):
    async def analyze_announcement(
        self,
        *,
        page_images: Sequence[AnnouncementPageImage],
        categories: Sequence[str],
        symbol: str,
        company: str,
        announcement_text: str,
        page_range_start: int,
        page_range_end: int,
        total_pages: int,
        provisional_summary: str | None = None,
        response_format_retry: bool = False,
    ) -> AnnouncementAnalysis: ...

    async def analyze_text_announcement(
        self,
        *,
        text: str,
        categories: Sequence[str],
        symbol: str,
        company: str,
        announcement_text: str,
        response_format_retry: bool = False,
    ) -> AnnouncementAnalysis: ...
