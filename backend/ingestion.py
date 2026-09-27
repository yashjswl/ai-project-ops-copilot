"""Turns an uploaded file into (raw_text, chunks) ready for embedding + extraction."""
import io

import docx
from pypdf import PdfReader

from backend.config import settings


def parse_file(filename: str, raw_bytes: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else "txt"

    if ext == "pdf":
        reader = PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == "docx":
        document = docx.Document(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in document.paragraphs)

    # txt, md, eml, or anything else treated as plain text
    return raw_bytes.decode("utf-8", errors="ignore")


def guess_source_type(filename: str) -> str:
    name = filename.lower()
    if "meeting" in name or "notes" in name:
        return "meeting_notes"
    if "status" in name or "report" in name:
        return "status_report"
    if "email" in name or name.endswith(".eml"):
        return "email"
    if "task" in name:
        return "task_list"
    if name.endswith(".pdf"):
        return "pdf"
    return "other"


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """Simple sliding-window chunker on whitespace-normalized text.

    Good enough for meeting notes / reports; swap for a semantic/markdown-aware
    splitter if ingesting long structured docs.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    text = " ".join(text.split())
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks
