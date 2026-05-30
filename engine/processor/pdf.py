from dataclasses import dataclass
from typing import cast

import fitz


@dataclass(slots=True)
class RenderedPdfPage:
    page_number: int
    media_type: str
    image_bytes: bytes


@dataclass(slots=True)
class RenderedPdfPages:
    total_pages: int
    pages: list[RenderedPdfPage]


def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pages = [cast(str, page.get_text("text")) for page in doc]
        return "\n".join(pages)
    finally:
        doc.close()


def render_pdf_pages(
    pdf_bytes: bytes,
    *,
    start_page: int,
    end_page: int,
    max_dimension_px: int,
    jpeg_quality: int,
) -> RenderedPdfPages:
    if start_page < 1:
        raise ValueError("start_page must be >= 1")
    if end_page < start_page:
        raise ValueError("end_page must be >= start_page")
    if max_dimension_px <= 0:
        raise ValueError("max_dimension_px must be > 0")
    if not 1 <= jpeg_quality <= 100:
        raise ValueError("jpeg_quality must be in range 1..100")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = doc.page_count
        if start_page > total_pages:
            raise ValueError(
                f"start_page ({start_page}) exceeds total_pages ({total_pages})"
            )
        clamped_end_page = min(end_page, total_pages)
        pages: list[RenderedPdfPage] = []

        for page_number in range(start_page, clamped_end_page + 1):
            page = doc.load_page(page_number - 1)
            rect = page.rect
            largest_dimension = max(rect.width, rect.height)
            zoom = (
                min(max_dimension_px / largest_dimension, 1.0)
                if largest_dimension
                else 1.0
            )
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            image_bytes = pixmap.tobytes("jpeg", jpg_quality=jpeg_quality)
            pages.append(
                RenderedPdfPage(
                    page_number=page_number,
                    media_type="image/jpeg",
                    image_bytes=image_bytes,
                )
            )

        return RenderedPdfPages(total_pages=total_pages, pages=pages)
    finally:
        doc.close()
