import pytest
from engine.processor.pdf import extract_pdf_text


def test_extract_returns_string_from_valid_pdf():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Infosys Q4 Results 2026")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_pdf_text(pdf_bytes)
    assert "Infosys" in result
    assert isinstance(result, str)


def test_extract_empty_pdf_returns_empty_string():
    import fitz
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_pdf_text(pdf_bytes)
    assert isinstance(result, str)


def test_extract_invalid_bytes_raises():
    with pytest.raises(Exception):
        extract_pdf_text(b"not a pdf")
