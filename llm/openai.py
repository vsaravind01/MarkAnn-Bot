import asyncio
import os
from collections.abc import Sequence

from openai import AsyncOpenAI, RateLimitError

from llm.provider import (
    AnnouncementAnalysis,
    AnnouncementPageImage,
    LLMContextWindowError,
    LLMRateLimitError,
    LLMResponseFormatError,
    parse_analysis_json,
)

_MAX_INLINE_RETRY_WAIT = 60.0

_ANALYSIS_SYSTEM = (
    "You are a financial analyst for Indian stock market announcements. "
    "Return ONLY a strict JSON object with keys: "
    "summary (string), category (string), confidence (high|medium|low), "
    "need_more_pages (boolean or null). "
    "Do not include markdown fences or any surrounding text."
)


class OpenAIProvider:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        # base_url lets the provider target any OpenAI-compatible server (e.g. a
        # local vLLM endpoint) instead of api.openai.com. Such servers ignore the
        # API key, so fall back to a placeholder when one is configured.
        base_url = os.environ.get("OPENAI_BASE_URL") or None
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key and base_url:
            key = "not-needed"
        self._client = AsyncOpenAI(api_key=key, base_url=base_url)
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")

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
    ) -> AnnouncementAnalysis:
        user_content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": _build_announcement_prompt(
                    categories=categories,
                    symbol=symbol,
                    company=company,
                    announcement_text=announcement_text,
                    page_range_start=page_range_start,
                    page_range_end=page_range_end,
                    total_pages=total_pages,
                    provisional_summary=provisional_summary,
                    response_format_retry=response_format_retry,
                ),
            }
        ]
        for image in page_images:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.mime_type};base64,{image.data_base64}"},
                }
            )

        payload = await self._create_completion(
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user", "content": user_content},
            ]
        )
        return parse_analysis_json(payload, categories=categories)

    async def analyze_text_announcement(
        self,
        *,
        text: str,
        categories: Sequence[str],
        symbol: str,
        company: str,
        announcement_text: str,
        response_format_retry: bool = False,
    ) -> AnnouncementAnalysis:
        payload = await self._create_completion(
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {
                    "role": "user",
                    "content": _build_text_prompt(
                        text=text,
                        categories=categories,
                        symbol=symbol,
                        company=company,
                        announcement_text=announcement_text,
                        response_format_retry=response_format_retry,
                    ),
                },
            ]
        )
        return parse_analysis_json(payload, categories=categories)

    async def _create_completion(self, messages: list[dict[str, object]]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=512,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            if _is_rate_limit_error(exc):
                retry_after = _extract_retry_after(exc)
                if retry_after is not None and retry_after <= _MAX_INLINE_RETRY_WAIT:
                    await asyncio.sleep(retry_after)
                    try:
                        response = await self._client.chat.completions.create(
                            model=self._model,
                            messages=messages,
                            max_tokens=512,
                            response_format={"type": "json_object"},
                        )
                    except Exception as exc2:
                        if _is_rate_limit_error(exc2):
                            raise LLMRateLimitError(
                                "Rate limited by OpenAI after retry.",
                                retry_after=_extract_retry_after(exc2),
                            ) from exc2
                        if _is_context_window_error(exc2):
                            raise LLMContextWindowError(
                                "Prompt exceeds the model context window."
                            ) from exc2
                        raise
                else:
                    raise LLMRateLimitError(
                        "Rate limited by OpenAI.", retry_after=retry_after
                    ) from exc
            elif _is_context_window_error(exc):
                raise LLMContextWindowError("Prompt exceeds the model context window.") from exc
            else:
                raise

        choices = getattr(response, "choices", None)
        if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)) or not choices:
            raise LLMResponseFormatError("OpenAI returned missing or invalid choices.")

        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = getattr(message, "content", None)
        content = content.strip() if isinstance(content, str) else ""
        if not content:
            raise LLMResponseFormatError("OpenAI returned empty content.")
        return content


def _is_rate_limit_error(exc: Exception) -> bool:
    return isinstance(exc, RateLimitError)


def _extract_retry_after(exc: Exception) -> float | None:
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    for key in ("retry-after", "Retry-After", "x-ratelimit-reset-requests"):
        value = headers.get(key)
        if value:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
    return None


def _build_announcement_prompt(
    *,
    categories: Sequence[str],
    symbol: str,
    company: str,
    announcement_text: str,
    page_range_start: int,
    page_range_end: int,
    total_pages: int,
    provisional_summary: str | None,
    response_format_retry: bool,
) -> str:
    categories_str = ", ".join(categories)
    provisional_summary_text = provisional_summary or "None"
    retry_instruction = (
        "This is a response-format retry. Return only the strict JSON object."
        if response_format_retry
        else ""
    )
    return (
        "Analyze this corporate announcement page range and classify it into one category.\n"
        f"Allowed categories: {categories_str}\n"
        f"Symbol: {symbol}\n"
        f"Company: {company}\n"
        f"Announcement text metadata: {announcement_text}\n"
        f"Current page range: {page_range_start}-{page_range_end}\n"
        f"Total pages in announcement: {total_pages}\n"
        f"Provisional summary from previous pages: {provisional_summary_text}\n"
        "need_more_pages behavior:\n"
        "- If page_range_end < total_pages, set need_more_pages=true only when additional pages are required for a reliable final analysis; otherwise false.\n"
        "- If page_range_end >= total_pages, set need_more_pages=false.\n"
        "- When provisional summary is provided, incorporate it with current-page evidence in the returned summary.\n"
        f"{retry_instruction}"
    )


def _build_text_prompt(
    *,
    text: str,
    categories: Sequence[str],
    symbol: str,
    company: str,
    announcement_text: str,
    response_format_retry: bool,
) -> str:
    categories_str = ", ".join(categories)
    retry_instruction = (
        "This is a response-format retry. Return only the strict JSON object."
        if response_format_retry
        else ""
    )
    return (
        "Analyze this text-only corporate announcement and classify it into one category.\n"
        f"Allowed categories: {categories_str}\n"
        f"Symbol: {symbol}\n"
        f"Company: {company}\n"
        f"Announcement text metadata: {announcement_text}\n"
        "Set need_more_pages to null for text-only analysis.\n\n"
        f"Announcement content:\n{text}\n"
        f"{retry_instruction}"
    )


def _is_context_window_error(exc: Exception) -> bool:
    if getattr(exc, "code", None) == "context_length_exceeded":
        return True
    message = str(exc).lower()
    markers = ("context length", "maximum context", "too many tokens", "prompt is too long")
    return any(marker in message for marker in markers)
