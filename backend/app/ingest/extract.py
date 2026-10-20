"""Turns an uploaded file into a list of (page number, text) pairs."""

import io
import re
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class ExtractionError(Exception):
    """A problem with the file the user can act on; the message is shown to them as-is."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based, matching what PDF viewers show
    text: str


SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def clean_text(raw: str) -> str:
    """Undo the line-wrapping PDFs bake into extracted text, keeping paragraph breaks."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated across lines
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)  # paragraph break
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # single newline inside a paragraph
    return text.strip()


def extract_pages(data: bytes, suffix: str, max_pages: int) -> list[Page]:
    if suffix == ".pdf":
        return _extract_pdf(data, max_pages)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExtractionError(
            "This text file isn't UTF-8 encoded. Re-save it as UTF-8 and upload again."
        ) from exc
    cleaned = clean_text(text)
    if not cleaned:
        raise ExtractionError("This file is empty.")
    return [Page(number=1, text=cleaned)]


def _extract_pdf(data: bytes, max_pages: int) -> list[Page]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError) as exc:
        raise ExtractionError("This file couldn't be read as a PDF. It may be damaged.") from exc

    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ExtractionError(
                    "This PDF is password-protected. Remove the password and upload it again."
                )
        except (PdfReadError, NotImplementedError) as exc:
            raise ExtractionError(
                "This PDF is password-protected. Remove the password and upload it again."
            ) from exc

    if len(reader.pages) > max_pages:
        raise ExtractionError(f"This PDF has {len(reader.pages)} pages. The limit is {max_pages}.")

    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = clean_text(page.extract_text() or "")
        except Exception:  # one malformed page shouldn't sink the whole document
            text = ""
        if text:
            pages.append(Page(number=index, text=text))

    if not pages:
        raise ExtractionError(
            "No selectable text found. This looks like a scanned PDF; DocMind needs PDFs with real text."
        )
    return pages
