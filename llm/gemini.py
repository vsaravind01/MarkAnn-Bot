import base64
import os
from collections.abc import Sequence

from google import genai
from google.genai import types

from llm.provider import (
    AnnouncementAnalysis,
    AnnouncementPageImage,
    LLMContextWindowError,
    LLMResponseFormatError,
    parse_analysis_json,
)

_ANALYSIS_INSTRUCTIONS = (
    "You are a financial analyst for Indian stock market announcements. "
    "Return ONLY a strict JSON object with keys: "
    "summary (string), category (string), confidence (high|medium|low), "
    "need_more_pages (boolean or null). "
    "Do not include markdown fences or any surrounding text."
)


class GeminiProvider:
    def __init__(self, api_key: str | None = None, model: str = "gemma-4-31b-it"):
        self._client = genai.Client(api_key=api_key or os.environ["GEMINI_API_KEY"])
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
        prompt = _build_announcement_prompt(
            categories=categories,
            symbol=symbol,
            company=company,
            announcement_text=announcement_text,
            page_range_start=page_range_start,
            page_range_end=page_range_end,
            total_pages=total_pages,
            provisional_summary=provisional_summary,
            response_format_retry=response_format_retry,
        )
        parts = [
            types.Part.from_text(text=f"{_ANALYSIS_INSTRUCTIONS}\n\n{prompt}")
        ]
        for image in page_images:
            image_bytes = base64.b64decode(image.data_base64)
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=image.mime_type))
        payload = await self._generate_content(
            contents=[types.Content(role="user", parts=parts)],
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
        prompt = _build_text_prompt(
            text=text,
            categories=categories,
            symbol=symbol,
            company=company,
            announcement_text=announcement_text,
            response_format_retry=response_format_retry,
        )
        payload = await self._generate_content(
            contents=f"{_ANALYSIS_INSTRUCTIONS}\n\n{prompt}",
        )
        return parse_analysis_json(payload, categories=categories)

    async def _generate_content(self, contents: str | list[types.Content]) -> str:
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
        except Exception as exc:
            if _is_context_window_error(exc):
                raise LLMContextWindowError("Prompt exceeds the model context window.") from exc
            raise

        payload = (response.text or "").strip()
        if not payload:
            raise LLMResponseFormatError("Gemini returned empty content.")
        return payload


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
    markers = ("context window", "maximum context", "too many tokens", "prompt is too long")
    return any(marker in message for marker in markers)
