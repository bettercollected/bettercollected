"""Reading the sign-in code from a code mail (pure: no network).

Only mails addressed to this run's plus-address count, and of those only the
newest one sent after the code was asked for. The code is the one
``[A-Z0-9]{3}-[A-Z0-9]{3}`` value in the mail's code box; a mail with no code
or with two different ones is refused rather than guessed at.
"""

from __future__ import annotations

import datetime as dt
import email
import email.policy
import email.utils
import html
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

CODE = r"[A-Z0-9]{3}-[A-Z0-9]{3}"
# the code alone between two tags (the template's code box)
BOXED_CODE = re.compile(r">\s*(" + CODE + r")\s*<")
LOOSE_CODE = re.compile(r"(?<![A-Za-z0-9])(" + CODE + r")(?![A-Za-z0-9])")
TAGS = re.compile(r"<(script|style)\b.*?</\1>|<[^>]+>", re.S | re.I)
# A sender's clock may run a little behind ours.
CLOCK_SKEW = dt.timedelta(minutes=2)


class CodeMailError(Exception):
    """The mail holds no unambiguous code (the message never quotes it)."""


@dataclass(frozen=True)
class MailMessage:
    id: str
    recipients: tuple[str, ...]
    date: Optional[dt.datetime]
    subject: str = ""
    html: str = field(default="", repr=False)
    text: str = field(default="", repr=False)


def _addresses(values: Iterable[str]) -> tuple[str, ...]:
    found = email.utils.getaddresses([v for v in values if v])
    return tuple(addr.strip().lower() for _, addr in found if addr)


def parse_message(message_id: str, raw: bytes) -> MailMessage:
    """An RFC 822 message as the parts the matcher needs."""
    message = email.message_from_bytes(raw, policy=email.policy.default)
    recipients = _addresses(
        [str(message.get(h, "")) for h in ("To", "Cc", "Delivered-To", "X-Original-To")]
    )
    date = None
    if message.get("Date"):
        try:
            date = email.utils.parsedate_to_datetime(str(message["Date"]))
            if date.tzinfo is None:
                date = date.replace(tzinfo=dt.timezone.utc)
        except (TypeError, ValueError):
            date = None
    html_part = message.get_body(preferencelist=("html",))
    text_part = message.get_body(preferencelist=("plain",))
    return MailMessage(
        id=message_id,
        recipients=recipients,
        date=date,
        subject=str(message.get("Subject", "")),
        html=html_part.get_content() if html_part is not None else "",
        text=text_part.get_content() if text_part is not None else "",
    )


def is_for(message: MailMessage, address: str) -> bool:
    return address.strip().lower() in message.recipients


def newest_code_mail(
    messages: Iterable[MailMessage], address: str, not_before: dt.datetime
) -> Optional[MailMessage]:
    """The newest mail to ``address`` dated at or after ``not_before`` (less
    the clock skew); mails to any other address, or older, are ignored."""
    earliest = not_before - CLOCK_SKEW
    candidates = [
        m
        for m in messages
        if is_for(m, address) and m.date is not None and m.date >= earliest
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda m: (m.date, m.id))


def extract_code(message: MailMessage) -> str:
    """The sign-in code of a code mail."""
    boxed = set(BOXED_CODE.findall(message.html))
    if len(boxed) == 1:
        return boxed.pop()
    visible = html.unescape(TAGS.sub(" ", message.html)) + "\n" + message.text
    loose = set(LOOSE_CODE.findall(visible))
    if len(loose) == 1:
        return loose.pop()
    if not loose and not boxed:
        raise CodeMailError("the code mail holds no sign-in code")
    raise CodeMailError("the code mail holds more than one code-like value")
