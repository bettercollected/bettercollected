"""The privacy policy link a form shows respondents.

Respondent forms render it as a link (webapp ``views/molecules/form/
trust-layer.tsx``), so only absolute http(s) URLs are stored: anything else
(``javascript:``, ``data:``, relative paths) is refused where it is saved.
"""

import re
from typing import Optional
from urllib.parse import urlsplit

MAX_POLICY_URL_LENGTH = 2048
_UNSAFE = re.compile(r"[\s\x00-\x1f\x7f]")


def checked_policy_url(url: Optional[str]) -> Optional[str]:
    """The trimmed URL, ``""`` for a blank one (which clears the link), or
    ``None`` when none was given. Raises ``ValueError`` for anything that
    isn't an absolute http(s) URL."""
    if url is None:
        return None
    url = url.strip()
    if not url:
        return ""
    if len(url) > MAX_POLICY_URL_LENGTH or _UNSAFE.search(url):
        raise ValueError("The privacy policy link must be an http(s) URL.")
    try:
        parts = urlsplit(url)
    except ValueError:
        raise ValueError("The privacy policy link must be an http(s) URL.")
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("The privacy policy link must be an http(s) URL.")
    return url
