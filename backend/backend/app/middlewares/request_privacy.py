"""What the request log may say about a request, and which responses must
never be cached.

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


def redact_receipts(text: str) -> str:
    """``text`` with the receipt number of any ``by-uuid`` path in it replaced."""
    return _RECEIPT_IN_TEXT.sub(rf"\1{REDACTED}", text)


def loggable_request(method: str, path: str) -> str:
    """The request as it is logged: method and redacted path, never the query
    string (search text, respondent emails)."""
    return redact_receipts(f"{method} {path}")


# Routes whose body is decrypted respondent data: the staff list of a form's
# submissions, the workspace-wide list, one submission, the bulk download and
# export, the flow view's paths and the receipt by number.
_RESPONSE_DATA_PATH = re.compile(
    r"/workspaces/[^/]+/(?:forms/[^/]+/)?"
    r"(?:submissions(?:/.*)?|all-submissions(?:/export)?|submission-paths)/?$"
)

NO_STORE_HEADERS: Final = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def carries_response_data(path: str) -> bool:
    """Whether the response of ``path`` may hold decrypted answers, and so
    must not be kept in a browser or proxy cache."""
    return _RESPONSE_DATA_PATH.search(path) is not None
