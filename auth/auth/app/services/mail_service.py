"""SMTP sending and the pieces every mail from this service shares.

Workspaces choose their own titles, so a title never reaches the From display
name or the subject (#761): the sender name is always this instance's
``ORGANIZATION_NAME``, subjects are fixed wording, and a workspace title only
appears in the body, on one line, capped and HTML-escaped.
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from fastapi_mail import ConnectionConfig, FastMail
from jinja2 import Environment, FileSystemLoader, select_autoescape

from auth.config import settings

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
MAX_TITLE_LENGTH = 200

_environment = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(default=True, default_for_string=True),
)


def one_line(value: Optional[str], limit: int = MAX_TITLE_LENGTH) -> Optional[str]:
    """Whitespace (line breaks included) collapsed, capped: safe for a
    subject header and a sentence."""
    if value is None:
        return None
    value = " ".join(value.split())
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return value or None


def sender_name() -> str:
    """The From display name of every mail: this instance's name, never a
    workspace's."""
    return one_line(settings.ORGANIZATION_NAME) or "BetterCollected"


def _squashed(value: Optional[str]) -> str:
    return "".join((value or "").split()).casefold()


def is_sender_name(title: Optional[str]) -> bool:
    """Whether ``title`` is just this instance's name ("BetterCollected" and
    "Better Collected" alike), so the body need not repeat it."""
    return bool(title) and _squashed(title) == _squashed(sender_name())


def render(template_name: str, **context) -> str:
    """A mail body from ``templates/``; every value is HTML-escaped."""
    return _environment.get_template(template_name).render(**context)


def _url_parts(url: Optional[str]):
    if not url or any(ch.isspace() or ch in "\"'<>\\" for ch in url):
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        return None
    return parts


def web_image_url(url: Optional[str]) -> Optional[str]:
    """``url`` when it is a plain http(s) URL, else None."""
    return url if _url_parts(url) else None


def storage_image_url(url: Optional[str]) -> Optional[str]:
    """``url`` when it points into this instance's own public storage
    (``MAIL_IMAGE_URL_PREFIXES``), else None: a caller-supplied image is
    only shown from there."""
    parts = _url_parts(url)
    if not parts or ".." in parts.path.split("/"):
        return None
    for prefix in (settings.MAIL_IMAGE_URL_PREFIXES or "").split(","):
        prefix = prefix.strip()
        base = _url_parts(prefix)
        if not base:
            continue
        if (
            parts.scheme == base.scheme
            and parts.netloc.lower() == base.netloc.lower()
            and parts.path.startswith(base.path.rstrip("/") + "/")
        ):
            return url
    return None


class MailService:
    def __init__(
        self,
        user=settings.mail_settings.user,
        password=settings.mail_settings.password,
        sender=settings.mail_settings.sender,
        smtp_port=settings.mail_settings.smtp_port,
        smtp_server=settings.mail_settings.smtp_server,
        mail_tls=settings.mail_settings.starttls,
        mail_ssl=settings.mail_settings.ssl_tls,
        use_credentials=settings.mail_settings.use_credentials,
        validate_certs=settings.mail_settings.validate_certs,
    ):
        mail_config = ConnectionConfig(
            MAIL_USERNAME=user,
            MAIL_PASSWORD=password,
            MAIL_FROM=sender,
            MAIL_PORT=smtp_port,
            MAIL_SERVER=smtp_server,
            # deliberately not a parameter: see the module docstring
            MAIL_FROM_NAME=sender_name(),
            MAIL_STARTTLS=mail_tls,
            MAIL_SSL_TLS=mail_ssl,
            USE_CREDENTIALS=use_credentials,
            VALIDATE_CERTS=validate_certs,
            TEMPLATE_FOLDER=os.getenv("TEMPLATE_FOLDER", "auth/app/templates"),
        )
        self.fast_mail = FastMail(mail_config)

    async def send_message(self, message):
        """Send a message whose body is already rendered (see ``render``)."""
        await self.fast_mail.send_message(message=message)
