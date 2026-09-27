"""What was uploaded, decided by the bytes, never by the file name or header."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Optional

from backend.app.services.pdf_import.analysis import DocumentRefused

_SIGNATURES = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
)


@dataclass(frozen=True)
class Upload:
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    title: str


def sniff(data: bytes) -> Optional[tuple]:
    head = data[:1024]
    # PDFs may carry junk before the header; readers accept it within 1 KB
    if b"%PDF-" in head:
        return "application/pdf", "pdf"
    for signature, content_type, extension in _SIGNATURES[1:]:
        if head.startswith(signature):
            return content_type, extension
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def title_from_file_name(file_name: Optional[str]) -> str:
    stem = (file_name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", stem)
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return (stem or "Imported form")[:120]


def inspect_upload(data: bytes, file_name: Optional[str], max_bytes: int) -> Upload:
    if not data:
        raise DocumentRefused("empty", "The uploaded file is empty.")
    if len(data) > max_bytes:
        raise DocumentRefused(
            "too_large", f"The file is larger than {max_bytes // (1024 * 1024)} MB."
        )
    kind = sniff(data)
    if kind is None:
        raise DocumentRefused(
            "unsupported_type", "Upload a PDF, or a PNG, JPEG or WebP photo of a form."
        )
    content_type, extension = kind
    return Upload(
        content_type=content_type,
        extension=extension,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        title=title_from_file_name(file_name),
    )
