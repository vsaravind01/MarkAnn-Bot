import io
import json

import requests
from pypdf import PdfReader


def extract_json_from_text(string: str) -> dict:
    """Extracts JSON from a given string.

    Args:
    -----
    string: str
        String containing JSON

    Returns:
    --------
    dict
        JSON extracted from the string
    """
    string = string[next(idx for idx, c in enumerate(string) if c in "{[") :]
    try:
        return json.loads(string)
    except json.JSONDecodeError as e:
        return json.loads(string[: e.pos])


def fetch_pdf_text_from_url(url, headers) -> str:
    """Fetches text from a PDF file hosted at a given URL.

    Args:
    -----
    url: str
        URL of the PDF file
    headers: dict
        Headers to be sent with the request

    Returns:
    --------
    str
        Text extracted from the PDF file
    """
    response = requests.get(url=url, headers=headers, timeout=120)
    on_fly_mem_obj = io.BytesIO(response.content)
    pdf_file = PdfReader(on_fly_mem_obj)
    text = ""
    for page in pdf_file.pages:
        text += page.extract_text().strip() + "\n"
    return text


def extract_pdf_text_from_file(file_path: str) -> str:
    """Extracts text from a given PDF file.

    Args:
    -----
    file_path: str
        Path to the PDF file

    Returns:
    --------
    str
        Text extracted from the PDF file
    """
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text().strip() + "\n"
    return text
