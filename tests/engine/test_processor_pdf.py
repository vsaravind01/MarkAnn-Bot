import fitz
import pytest

from engine.processors.pdf import extract_pdf_text, render_pdf_pages


def _make_pdf(page_count: int) -> bytes:
    doc = fitz.open()
    for index in range(page_count):
        page = doc.new_page()
        page.insert_text((50, 50), f"Announcement page {index + 1}")
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_returns_string_from_valid_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Infosys Q4 Results 2026")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_pdf_text(pdf_bytes)
    assert "Infosys" in result
    assert isinstance(result, str)


def test_extract_empty_pdf_returns_empty_string():
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    result = extract_pdf_text(pdf_bytes)
    assert isinstance(result, str)
    assert result.strip() == ""


def test_extract_invalid_bytes_raises():
    with pytest.raises(fitz.FileDataError):
        extract_pdf_text(b"not a pdf")


def test_render_pdf_pages_returns_jpeg_images_for_requested_range():
    result = render_pdf_pages(
        _make_pdf(3),
        start_page=1,
        end_page=2,
        max_dimension_px=900,
        jpeg_quality=60,
    )

    assert result.total_pages == 3
    assert [page.page_number for page in result.pages] == [1, 2]
    assert all(page.media_type == "image/jpeg" for page in result.pages)
    assert all(page.image_bytes.startswith(b"\xff\xd8") for page in result.pages)


def test_render_pdf_pages_clamps_end_page_to_total_pages():
    result = render_pdf_pages(
        _make_pdf(2),
        start_page=2,
        end_page=10,
        max_dimension_px=900,
        jpeg_quality=60,
    )

    assert result.total_pages == 2
    assert [page.page_number for page in result.pages] == [2]


def test_render_pdf_pages_rejects_invalid_range():
    with pytest.raises(ValueError, match="start_page must be >= 1"):
        render_pdf_pages(
            _make_pdf(1),
            start_page=0,
            end_page=1,
            max_dimension_px=900,
            jpeg_quality=60,
        )

    with pytest.raises(ValueError, match="end_page must be >= start_page"):
        render_pdf_pages(
            _make_pdf(1),
            start_page=2,
            end_page=1,
            max_dimension_px=900,
            jpeg_quality=60,
        )


@pytest.mark.parametrize("max_dimension_px", [0, -100])
def test_render_pdf_pages_rejects_invalid_max_dimension(max_dimension_px: int):
    with pytest.raises(ValueError, match="max_dimension_px must be > 0"):
        render_pdf_pages(
            _make_pdf(1),
            start_page=1,
            end_page=1,
            max_dimension_px=max_dimension_px,
            jpeg_quality=60,
        )


@pytest.mark.parametrize("jpeg_quality", [0, 101])
def test_render_pdf_pages_rejects_invalid_jpeg_quality(jpeg_quality: int):
    with pytest.raises(ValueError, match=r"jpeg_quality must be in range 1\.\.100"):
        render_pdf_pages(
            _make_pdf(1),
            start_page=1,
            end_page=1,
            max_dimension_px=900,
            jpeg_quality=jpeg_quality,
        )


def test_render_pdf_pages_rejects_start_page_beyond_total_pages():
    with pytest.raises(
        ValueError,
        match=r"start_page \(3\) exceeds total_pages \(2\)",
    ):
        render_pdf_pages(
            _make_pdf(2),
            start_page=3,
            end_page=3,
            max_dimension_px=900,
            jpeg_quality=60,
        )


def test_render_pdf_pages_respects_max_dimension_invariant():
    max_dimension_px = 200
    result = render_pdf_pages(
        _make_pdf(2),
        start_page=1,
        end_page=2,
        max_dimension_px=max_dimension_px,
        jpeg_quality=60,
    )

    for rendered_page in result.pages:
        pixmap = fitz.Pixmap(rendered_page.image_bytes)
        assert max(pixmap.width, pixmap.height) <= max_dimension_px


def test_render_pdf_pages_invalid_bytes_raises():
    with pytest.raises(fitz.FileDataError):
        render_pdf_pages(
            b"not a pdf",
            start_page=1,
            end_page=1,
            max_dimension_px=900,
            jpeg_quality=60,
        )
