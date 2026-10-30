"""What the request log may say about a request.

A receipt number (``/submissions/by-uuid/<number>``) opens a response's
answers without a sign-in, and the search box sends a respondent's email as a
query parameter. Neither may reach the logs, whose readers are wider than the
database's access rules.
"""

import re
from typing import Final

REDACTED: Final = "<redacted>"

# the receipt number in the path of every by-uuid route (read and deletion request)
_RECEIPT_IN_TEXT = re.compile(r"(/by-uuid/)[^/?#\s<>\"']+")
# defence in depth: a receipt number (a UUID) pasted where a response id goes,
# /submissions/{id}; response ids are not UUID-shaped
_RECEIPT_AS_RESPONSE_ID = re.compile(
    r"(/submissions/)[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?![0-9a-zA-Z-])"
)


def redact_receipts(text: str) -> str:
    """``text`` with the receipt number of any ``by-uuid`` path in it replaced,
    and any UUID-shaped segment straight after ``/submissions/``."""
    text = _RECEIPT_IN_TEXT.sub(rf"\1{REDACTED}", text)
    return _RECEIPT_AS_RESPONSE_ID.sub(rf"\1{REDACTED}", text)


def loggable_request(method: str, path: str) -> str:
    """The request as it is logged: method and redacted path, never the query
    string (search text, respondent emails)."""
    return redact_receipts(f"{method} {path}")
