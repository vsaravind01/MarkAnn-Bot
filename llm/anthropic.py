import os
from collections.abc import Sequence

import anthropic as _anthropic

from llm.provider import (
    AnnouncementAnalysis,
    AnnouncementPageImage,
    LLMContextWindowError,
    LLMResponseFormatError,
    parse_analysis_json,
)

_ANALYSIS_SYSTEM = (
    "You are a financial analyst for Indian stock market announcements. "
    "Return ONLY a strict JSON object with keys: "
    "summary (string), category (string), confidence (high|medium|low), "
    "need_more_pages (boolean or null). "
    "Do not include markdown fences or any surrounding text."
)


class AnthropicProvider:
    def __init__(self, api_key: str | None = None, model: str = "claude-opus-4-7"):
        self._client = _anthropic.AsyncAnthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"]
        )
        self._model = model

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
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image.mime_type,
                        "data": image.data_base64,
                    },
                }
            )
        payload = await self._create_message(user_content)
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
        payload = await self._create_message(
            _build_text_prompt(
                text=text,
                categories=categories,
                symbol=symbol,
                company=company,
                announcement_text=announcement_text,
                response_format_retry=response_format_retry,
            )
        )
        return parse_analysis_json(payload, categories=categories)

    async def _create_message(self, content: str | list[dict[str, object]]) -> str:
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=512,
                system=_ANALYSIS_SYSTEM,
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:
            if _is_context_window_error(exc):
                raise LLMContextWindowError("Prompt exceeds the model context window.") from exc
            raise

        if not message.content:
            raise LLMResponseFormatError("Anthropic returned no content blocks.")

        text_block = next(
            (block for block in message.content if getattr(block, "type", None) == "text"),
            None,
        )
        if text_block is None:
            raise LLMResponseFormatError("Anthropic returned no text content blocks.")

        text = getattr(text_block, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise LLMResponseFormatError("Anthropic returned empty text content block.")
        return text.strip()


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
    message = str(exc).lower()
    markers = ("prompt is too long", "context window", "maximum context", "too many tokens")
    return any(marker in message for marker in markers)
