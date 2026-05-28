import fitz


def extract_pdf_text(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages: list[str] = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages)
