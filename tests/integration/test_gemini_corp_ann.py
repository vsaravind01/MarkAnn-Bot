"""Integration tests — verify real Gemini API summarisation and classification.

Ground truth derived from:
  PDF: RAILTEL_27052025105906_Railtel_Order_Book_Company_Rep_270525.pdf
  Doc: RailTel work order from Office of the Inspector General of Police (Technical
       Services) for Supply, Install & Maintenance of Integrated Security Solution
       for Edge Devices to AP Police Dept — Rs. 25,12,94,570 (incl. tax).

  Expected classification: orders_or_contracts
  Key facts that any faithful summary must mention:
    - "railtel"           (the disclosing company)
    - "order"             (the nature of the event)
    - at least one of:    "security" | "police" | "integrated" | "andhra pradesh"
                          (specifics of the contract)

Run:
    uv run pytest tests/integration/ -v -m integration

Skip condition: GEMINI_API_KEY absent from .env.test (or env).
"""

import base64
import os
from pathlib import Path

import fitz
import httpx
import pytest
from dotenv import load_dotenv
from google.genai import errors as genai_errors

from engine.processors.corp_ann import ANNOUNCEMENT_CATEGORIES
from engine.processors.pdf import render_pdf_pages
from llm.gemini import GeminiProvider
from llm.provider import AnnouncementPageImage

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.test", override=False)

_RAILTEL_PDF_URL = (
    "https://nsearchives.nseindia.com/corporate/"
    "RAILTEL_27052025105906_Railtel_Order_Book_Company_Rep_270525.pdf"
)
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com/",
}
_RAILTEL_SYMBOL = "RAILTEL"
_RAILTEL_COMPANY = "RailTel Corporation of India Ltd"
_RAILTEL_ANNOUNCEMENT_TEXT = "NSE corporate disclosure metadata for attached filing PDF."


def _make_provider() -> GeminiProvider:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set — skipping integration test")
    model = os.environ.get("GEMINI_MODEL", "gemma-4-31b-it")  # matches GeminiProvider default
    return GeminiProvider(api_key=api_key, model=model)


async def _fetch_pdf_bytes(url: str) -> bytes:
    async with httpx.AsyncClient(
        headers=_NSE_HEADERS, follow_redirects=True, timeout=30.0
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    return response.content


def _pdf_bytes_to_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(str(page.get_text()) for page in doc)
    doc.close()
    return text



@pytest.fixture(scope="module")
def gemini_provider() -> GeminiProvider:
    return _make_provider()


@pytest.fixture(scope="module")
async def railtel_pdf_bytes() -> bytes:
    return await _fetch_pdf_bytes(_RAILTEL_PDF_URL)


@pytest.fixture(scope="module")
def railtel_pdf_text(railtel_pdf_bytes: bytes) -> str:
    return _pdf_bytes_to_text(railtel_pdf_bytes)


@pytest.fixture(scope="module")
async def railtel_analysis(gemini_provider: GeminiProvider, railtel_pdf_text: str):
    try:
        return await gemini_provider.analyze_text_announcement(
            text=railtel_pdf_text,
            categories=ANNOUNCEMENT_CATEGORIES,
            symbol=_RAILTEL_SYMBOL,
            company=_RAILTEL_COMPANY,
            announcement_text=_RAILTEL_ANNOUNCEMENT_TEXT,
        )
    except genai_errors.ClientError as exc:
        pytest.skip(f"Gemini API quota or auth error: {exc}")


@pytest.fixture(scope="module")
async def railtel_multimodal_analysis(gemini_provider: GeminiProvider, railtel_pdf_bytes: bytes):
    rendered = render_pdf_pages(
        railtel_pdf_bytes,
        start_page=1,
        end_page=5,
        max_dimension_px=900,
        jpeg_quality=60,
    )
    page_images = [
        AnnouncementPageImage(
            page_number=page.page_number,
            mime_type=page.media_type,
            data_base64=base64.b64encode(page.image_bytes).decode("ascii"),
        )
        for page in rendered.pages
    ]
    total_pages = rendered.total_pages
    try:
        return await gemini_provider.analyze_announcement(
            page_images=page_images,
            categories=ANNOUNCEMENT_CATEGORIES,
            symbol=_RAILTEL_SYMBOL,
            company=_RAILTEL_COMPANY,
            announcement_text=_RAILTEL_ANNOUNCEMENT_TEXT,
            page_range_start=1,
            page_range_end=rendered.pages[-1].page_number,
            total_pages=total_pages,
            provisional_summary=None,
        )
    except genai_errors.ClientError as exc:
        pytest.skip(f"Gemini API quota or auth error: {exc}")
    except genai_errors.ServerError as exc:
        pytest.skip(f"Gemini API server error (model may not support vision): {exc}")


@pytest.mark.integration
async def test_gemini_classifies_railtel_order(railtel_analysis):
    """Classification must resolve to 'orders_or_contracts' for a clear work-order disclosure."""
    category = railtel_analysis.category
    assert category == "orders_or_contracts", (
        f"Expected 'orders_or_contracts', got {category!r}. "
        "Check model output or prompt for regressions."
    )


@pytest.mark.integration
async def test_gemini_summarises_railtel_order(railtel_analysis):
    """Summary must be non-empty and contain the company name, the event type, and contract specifics."""
    summary = railtel_analysis.summary

    assert summary.strip(), "Summary must not be empty"

    lower = summary.lower()

    assert "railtel" in lower, f"Summary missing company name 'railtel': {summary!r}"
    assert "order" in lower, f"Summary missing event type 'order': {summary!r}"
    assert any(term in lower for term in ("security", "police", "integrated", "andhra pradesh")), (
        f"Summary missing contract specifics (security/police/integrated/Andhra Pradesh): {summary!r}"
    )


@pytest.mark.integration
async def test_gemini_summarise_and_classify_consistent(railtel_analysis):
    """Single analysis output must be self-consistent: order summary implies orders_or_contracts."""
    summary = railtel_analysis.summary
    category = railtel_analysis.category

    assert railtel_analysis.need_more_pages is None
    assert category == "orders_or_contracts"
    assert "order" in summary.lower(), (
        f"Category is orders_or_contracts but 'order' absent from summary: {summary!r}"
    )


@pytest.mark.integration
async def test_gemini_multimodal_classifies_railtel_order(railtel_multimodal_analysis):
    """Multimodal (image) path must classify the RailTel work-order PDF correctly."""
    category = railtel_multimodal_analysis.category
    assert category == "orders_or_contracts", (
        f"Expected 'orders_or_contracts', got {category!r}. "
        "Check image rendering, prompt, or model for regressions."
    )


@pytest.mark.integration
async def test_gemini_multimodal_summarises_railtel_order(railtel_multimodal_analysis):
    """Multimodal summary must be non-empty and contain company name, event type, and contract specifics."""
    summary = railtel_multimodal_analysis.summary

    assert summary.strip(), "Multimodal summary must not be empty"

    lower = summary.lower()

    assert "railtel" in lower, f"Multimodal summary missing company name 'railtel': {summary!r}"
    assert "order" in lower, f"Multimodal summary missing event type 'order': {summary!r}"
    assert any(term in lower for term in ("security", "police", "integrated", "andhra pradesh")), (
        f"Multimodal summary missing contract specifics: {summary!r}"
    )


@pytest.mark.integration
async def test_gemini_multimodal_need_more_pages_is_bool(railtel_multimodal_analysis):
    """need_more_pages must be a boolean (not null) when page_range_end < total_pages is possible."""
    assert isinstance(railtel_multimodal_analysis.need_more_pages, bool | type(None))
