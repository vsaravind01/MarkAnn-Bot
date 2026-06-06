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
    uv run pytest tests/integration/ -v

Skip condition: GEMINI_API_KEY absent from .env.test (or env).
"""

import os
from pathlib import Path

import fitz
import httpx
import pytest
from dotenv import load_dotenv

from engine.processors.corp_ann import ANNOUNCEMENT_CATEGORIES
from llm.gemini import GeminiProvider

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
    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
    return GeminiProvider(api_key=api_key, model=model)


async def _fetch_pdf_text(url: str) -> str:
    async with httpx.AsyncClient(
        headers=_NSE_HEADERS, follow_redirects=True, timeout=30.0
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = "\n".join(str(page.get_text()) for page in doc)
    doc.close()
    return text


async def _analyze_railtel_text(provider: GeminiProvider, text: str):
    return await provider.analyze_text_announcement(
        text=text,
        categories=ANNOUNCEMENT_CATEGORIES,
        symbol=_RAILTEL_SYMBOL,
        company=_RAILTEL_COMPANY,
        announcement_text=_RAILTEL_ANNOUNCEMENT_TEXT,
    )


@pytest.fixture(scope="module")
def gemini_provider() -> GeminiProvider:
    return _make_provider()


@pytest.fixture(scope="module")
async def railtel_pdf_text() -> str:
    return await _fetch_pdf_text(_RAILTEL_PDF_URL)


@pytest.fixture(scope="module")
async def railtel_analysis(gemini_provider: GeminiProvider, railtel_pdf_text: str):
    return await _analyze_railtel_text(gemini_provider, railtel_pdf_text)


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
