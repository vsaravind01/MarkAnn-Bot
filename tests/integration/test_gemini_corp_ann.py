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
    - at least one of:    "security" | "police" | "ap" | "integrated"
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

from engine.processor.corp_ann import ANNOUNCEMENT_CATEGORIES
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


def _make_provider() -> GeminiProvider:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set — skipping integration test")
    model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
    return GeminiProvider(api_key=api_key, model=model)


async def _fetch_pdf_text(url: str) -> str:
    async with httpx.AsyncClient(headers=_NSE_HEADERS, follow_redirects=True, timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = "\n".join(str(page.get_text()) for page in doc)
    doc.close()
    return text


@pytest.mark.integration
async def test_gemini_classifies_railtel_order():
    """Classification must resolve to 'orders_or_contracts' for a clear work-order disclosure."""
    provider = _make_provider()
    text = await _fetch_pdf_text(_RAILTEL_PDF_URL)
    category = await provider.classify(text, ANNOUNCEMENT_CATEGORIES)
    assert category == "orders_or_contracts", (
        f"Expected 'orders_or_contracts', got {category!r}. "
        "Check model output or prompt for regressions."
    )


@pytest.mark.integration
async def test_gemini_summarises_railtel_order():
    """Summary must be non-empty and contain the company name, the event type, and contract specifics."""
    provider = _make_provider()
    text = await _fetch_pdf_text(_RAILTEL_PDF_URL)
    summary = await provider.summarize(text)

    assert summary.strip(), "Summary must not be empty"

    lower = summary.lower()

    assert "railtel" in lower, (
        f"Summary missing company name 'railtel': {summary!r}"
    )
    assert "order" in lower, (
        f"Summary missing event type 'order': {summary!r}"
    )
    assert any(term in lower for term in ("security", "police", "ap", "integrated")), (
        f"Summary missing contract specifics (security/police/AP/integrated): {summary!r}"
    )


@pytest.mark.integration
async def test_gemini_summarise_and_classify_consistent():
    """Both calls on the same document must agree: an order summary implies orders_or_contracts."""
    provider = _make_provider()
    text = await _fetch_pdf_text(_RAILTEL_PDF_URL)

    summary = await provider.summarize(text)
    category = await provider.classify(text, ANNOUNCEMENT_CATEGORIES)

    assert category == "orders_or_contracts"
    assert "order" in summary.lower(), (
        f"Category is orders_or_contracts but 'order' absent from summary: {summary!r}"
    )
