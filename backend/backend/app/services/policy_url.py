"""The privacy policy link a form shows respondents.

Respondent forms render it as a link (webapp ``views/molecules/form/
trust-layer.tsx``), so only absolute http(s) URLs are stored: anything else
(``javascript:``, ``data:``, relative paths) is refused where it is saved.
The ending page's button link follows the same rule.
"""

import re
from typing import Optional
from urllib.parse import urlsplit

MAX_POLICY_URL_LENGTH = 2048
_UNSAFE = re.compile(r"[\s\x00-\x1f\x7f]")


def _checked_http_url(url: Optional[str], message: str) -> Optional[str]:
    if url is None:
        return None
    url = url.strip()
    if not url:
        return ""
    if len(url) > MAX_POLICY_URL_LENGTH or _UNSAFE.search(url):
        raise ValueError(message)
    try:
        parts = urlsplit(url)
    except ValueError:
        raise ValueError(message)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError(message)
    return url


def checked_policy_url(url: Optional[str]) -> Optional[str]:
    """The trimmed URL, ``""`` for a blank one (which clears the link), or
    ``None`` when none was given. Raises ``ValueError`` for anything that
    isn't an absolute http(s) URL."""
    return _checked_http_url(url, "The privacy policy link must be an http(s) URL.")


def checked_button_link(url: Optional[str]) -> Optional[str]:
    """The ending page's button link, under the same rule as the privacy
    policy link: an absolute http(s) URL, ``""`` for a blank one, ``None``
    when none was given; ``ValueError`` otherwise. Respondents' browsers open
    it from the ending page (webapp ``views/organism/form/thankyou-page.tsx``)."""
    return _checked_http_url(url, "The ending button's link must be an http(s) URL.")
