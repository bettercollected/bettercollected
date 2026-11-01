"""What the export routes and the PDF route say about a file they hand out."""

from urllib.parse import quote

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"}


def attachment(file_name: str) -> str:
    """``Content-Disposition`` for a name made from a form title: a plain ASCII
    fallback and the full name percent-encoded (never a raw character of the
    title in the header)."""
    ascii_name = "".join(c if c.isascii() and c.isprintable() and c not in '"\;' else "_" for c in file_name)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name, safe='')}"
