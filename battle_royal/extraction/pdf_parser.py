"""Extract raw text from CV/LinkedIn PDF files using pdfplumber."""

from pathlib import Path
from typing import Union

import pdfplumber


def extract_text_from_pdf(pdf_path: Union[str, Path]) -> str:
    """Extract all text from a PDF file.

    Handles multi-column LinkedIn exports by using pdfplumber's
    default text extraction which reads left-to-right, top-to-bottom.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)

    full_text = "\n\n".join(pages_text)
    if not full_text.strip():
        raise ValueError(f"No text extracted from {pdf_path}")

    return full_text
