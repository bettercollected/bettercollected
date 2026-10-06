"""Notification mails the backend asks for on behalf of a signed-in user.

Not a relay: the caller names a recipient and a few plain-text values, never
a subject or a body. The mail is a fixed template, every value is HTML-escaped,
and the one link must point at a submission page on a host this service is
configured with (``CLIENT_URL`` / ``CLIENT_ADMIN_URL``).

Custom domains are deliberately not accepted as link hosts: nothing here can
tell that a domain belongs to the workspace, so the backend always links to
the client host, which serves every workspace's pages too.
"""

import re
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from fastapi_mail import MessageSchema
from loguru import logger

from auth.app.services.mail_service import (  # noqa: F401 — one_line re-exported
    MailService,
    one_line,
    render,
)
from auth.config import settings

SUBMISSION_UPDATE_TEMPLATE = "submission_update.html"
# /<workspace handle>/submissions/<response id>, as the backend builds it
_SUBMISSION_PATH = re.compile(
    r"/[A-Za-z0-9._~%-]{1,200}/submissions/[A-Za-z0-9-]{1,64}"
)
# Per signed-in sender and process: a burst guard, not an accounting limit.
NOTICES_PER_HOUR = 300


def _origin_and_prefix(base_url: Optional[str]) -> Optional[Tuple[str, str]]:
    if not base_url:
        return None
    parts = urlsplit(base_url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower(), parts.path.rstrip("/")


def allowed_link_bases() -> List[Tuple[str, str]]:
    bases = [
        _origin_and_prefix(settings.CLIENT_URL),
        _origin_and_prefix(settings.CLIENT_ADMIN_URL),
    ]
    return [base for base in bases if base]


def is_allowed_submission_link(link: str) -> bool:
    """A link to a submission page on one of the configured hosts: http(s),
    no credentials, query or fragment, and the exact path shape."""
    try:
        parts = urlsplit(link)
    except ValueError:
        return False
    if (
        parts.scheme not in ("http", "https")
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
    ):
        return False
    origin = f"{parts.scheme}://{parts.netloc}".lower()
    for base_origin, prefix in allowed_link_bases():
        if origin != base_origin or not parts.path.startswith(prefix + "/"):
            continue
        if _SUBMISSION_PATH.fullmatch(parts.path[len(prefix) :]):
            return True
    return False


def render_submission_update(
    form_title: str, workspace_title: Optional[str], link: str
) -> str:
    return render(
        SUBMISSION_UPDATE_TEMPLATE,
        form_title=one_line(form_title),
        workspace_title=one_line(workspace_title),
        link=link,
    )


class NotificationService:
    def __init__(self):
        self._sent: Dict[str, Deque[float]] = defaultdict(deque)

    def allow(self, sender_id: str) -> bool:
        """Count one notice for ``sender_id``; False once over the hourly cap."""
        now = time.monotonic()
        sent = self._sent[sender_id]
        while sent and now - sent[0] > 3600:
            sent.popleft()
        if len(sent) >= NOTICES_PER_HOUR:
            return False
        sent.append(now)
        return True

    async def send_submission_update(
        self,
        recipient: str,
        form_title: str,
        workspace_title: Optional[str],
        link: str,
    ) -> None:
        """Email ``recipient`` that their submission has an update. Runs after
        the response was sent: failures are logged without the address."""
        try:
            message = MessageSchema(
                # fixed wording: the form and workspace titles are chosen by
                # the workspace and appear only in the body (#761)
                subject="Update on your submission",
                recipients=[recipient],
                body=render_submission_update(form_title, workspace_title, link),
                subtype="html",
            )
            # The sender name is always this instance's (MailService): a
            # workspace title would let anyone with a workspace pose as any
            # sender. It appears only in the body.
            await MailService().send_message(message)
        except Exception as exc:  # noqa: BLE001 — background task, nothing to answer
            logger.warning(f"Submission update notice not sent ({type(exc).__name__})")
