"""The suite's configuration: environment variables only (docs/smoke-test.md).

Secrets (GitHub environment `production-smoke`):
  SMOKE_API_KEY                 scoped API key of the test workspace
  SMOKE_IMAP_APP_PASSWORD       Gmail app password (IMAP), or instead
  SMOKE_GMAIL_CLIENT_ID, SMOKE_GMAIL_CLIENT_SECRET, SMOKE_GMAIL_REFRESH_TOKEN
                                Gmail API with gmail.readonly
Variables:
  SMOKE_APP_URL                 the web app (https://admin.example.com)
  SMOKE_MAILBOX                 the test mailbox's base address
  SMOKE_WORKSPACE_ID            the test workspace's id or name (handle)
  SMOKE_CUSTOM_DOMAIN           the test workspace's custom domain
  SMOKE_GOOGLE_FORM_ID          the edit id of the test Google Form

Exactly one mailbox set must be present. A local dry run reads codes from a
Mailpit inbox instead (``--mailpit``), and then no mailbox secret may be set.
"""

from __future__ import annotations

import os
import re
import secrets
from dataclasses import dataclass, field
from typing import Mapping, Optional
from urllib.parse import urlsplit, urlunsplit

IMAP = "imap"
GMAIL_API = "gmail-api"
MAILPIT = "mailpit"

GMAIL_KEYS = (
    "SMOKE_GMAIL_CLIENT_ID",
    "SMOKE_GMAIL_CLIENT_SECRET",
    "SMOKE_GMAIL_REFRESH_TOKEN",
)
GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}
OBJECT_ID = re.compile(r"^[0-9a-f]{24}$")
ADDRESS = re.compile(r"^([A-Za-z0-9._%-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})$")
HANDLE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
DOMAIN = re.compile(
    r"^(?=.{1,253}$)(([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}|localhost|127\.0\.0\.1)(:\d{1,5})?$"
)
GOOGLE_FORM_ID = re.compile(r"^[A-Za-z0-9_-]{10,200}$")


class ConfigError(Exception):
    """A missing or malformed setting; the message names it, never its value."""


@dataclass(frozen=True)
class MailboxSettings:
    kind: str
    address: str
    # IMAP
    imap_host: str = ""
    app_password: str = field(default="", repr=False)
    # Gmail API
    client_id: str = field(default="", repr=False)
    client_secret: str = field(default="", repr=False)
    refresh_token: str = field(default="", repr=False)
    # Mailpit (local dry run)
    mailpit_url: str = ""


@dataclass(frozen=True)
class Config:
    app_url: str
    api_url: Optional[str]
    api_key: str = field(repr=False)
    workspace: str
    custom_domain: str
    google_form_id: str
    mailbox: MailboxSettings
    run_tag: str

    @property
    def run_address(self) -> str:
        return plus_address(self.mailbox.address, self.run_tag)

    def secrets(self) -> list[str]:
        m = self.mailbox
        return [
            v
            for v in (
                self.api_key,
                m.app_password,
                m.client_id,
                m.client_secret,
                m.refresh_token,
            )
            if v
        ]


def _get(env: Mapping[str, str], name: str) -> str:
    return (env.get(name) or "").strip()


def _required(env: Mapping[str, str], name: str) -> str:
    value = _get(env, name)
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def normalize_url(value: str, name: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError(f"{name} must be an http(s) URL")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise ConfigError(f"{name} must be a plain base URL")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


def plus_address(base: str, tag: str) -> str:
    """``name@domain`` + ``tag`` -> ``name+tag@domain``."""
    match = ADDRESS.match(base)
    if not match:
        raise ConfigError("SMOKE_MAILBOX must be a plain address (name@domain)")
    if not re.fullmatch(r"[a-z0-9-]{1,40}", tag):
        raise ConfigError("the run tag must be 1-40 lower-case letters, digits or -")
    local, domain = match.groups()
    return f"{local}+{tag}@{domain}"


def run_tag(env: Mapping[str, str]) -> str:
    """Unique per run: the Actions run id and attempt, plus randomness (a
    rerun of the same attempt, or a local run, never reuses an address)."""
    run_id = re.sub(r"[^0-9]", "", _get(env, "GITHUB_RUN_ID"))[:20]
    attempt = re.sub(r"[^0-9]", "", _get(env, "GITHUB_RUN_ATTEMPT"))[:4]
    suffix = secrets.token_hex(3)
    if run_id:
        return f"smoke-{run_id}-{attempt or '1'}-{suffix}"
    return f"smoke-local-{suffix}"


def mailbox_settings(
    env: Mapping[str, str], address: str, mailpit_url: Optional[str] = None
) -> MailboxSettings:
    app_password = _get(env, "SMOKE_IMAP_APP_PASSWORD")
    gmail = {k: _get(env, k) for k in GMAIL_KEYS}
    gmail_given = [k for k, v in gmail.items() if v]
    if mailpit_url:
        if app_password or gmail_given:
            raise ConfigError(
                "--mailpit is for a local dry run: unset the mailbox secrets "
                "(SMOKE_IMAP_APP_PASSWORD, SMOKE_GMAIL_*) first"
            )
        return MailboxSettings(
            kind=MAILPIT,
            address=address,
            mailpit_url=normalize_url(mailpit_url, "--mailpit"),
        )
    if gmail_given and len(gmail_given) != len(GMAIL_KEYS):
        missing = ", ".join(k for k in GMAIL_KEYS if k not in gmail_given)
        raise ConfigError(f"the Gmail API mailbox is incomplete: {missing} not set")
    if app_password and gmail_given:
        raise ConfigError(
            "both mailbox sets are set (SMOKE_IMAP_APP_PASSWORD and "
            "SMOKE_GMAIL_*): keep exactly one"
        )
    if not app_password and not gmail_given:
        raise ConfigError(
            "no mailbox is configured: set SMOKE_IMAP_APP_PASSWORD, or "
            "SMOKE_GMAIL_CLIENT_ID, SMOKE_GMAIL_CLIENT_SECRET and "
            "SMOKE_GMAIL_REFRESH_TOKEN"
        )
    if app_password:
        domain = address.rsplit("@", 1)[1].lower()
        if domain not in GMAIL_DOMAINS:
            raise ConfigError("IMAP is supported for a Gmail mailbox only")
        return MailboxSettings(
            kind=IMAP,
            address=address,
            imap_host="imap.gmail.com",
            app_password=app_password,
        )
    return MailboxSettings(
        kind=GMAIL_API,
        address=address,
        client_id=gmail["SMOKE_GMAIL_CLIENT_ID"],
        client_secret=gmail["SMOKE_GMAIL_CLIENT_SECRET"],
        refresh_token=gmail["SMOKE_GMAIL_REFRESH_TOKEN"],
    )


def load(
    env: Mapping[str, str] = os.environ,
    *,
    target: Optional[str] = None,
    api_url: Optional[str] = None,
    mailpit_url: Optional[str] = None,
    tag: Optional[str] = None,
) -> Config:
    app_url = normalize_url(target or _required(env, "SMOKE_APP_URL"), "SMOKE_APP_URL")
    api_key = _required(env, "SMOKE_API_KEY")
    if not re.fullmatch(r"bc_[A-Za-z0-9]{16,128}", api_key):
        raise ConfigError("SMOKE_API_KEY does not look like a workspace API key")
    address = _required(env, "SMOKE_MAILBOX")
    if not ADDRESS.match(address):
        raise ConfigError("SMOKE_MAILBOX must be a plain address (name@domain)")
    workspace = _required(env, "SMOKE_WORKSPACE_ID")
    if not (OBJECT_ID.match(workspace) or HANDLE.match(workspace)):
        raise ConfigError("SMOKE_WORKSPACE_ID must be a workspace id or name")
    custom_domain = _required(env, "SMOKE_CUSTOM_DOMAIN").lower()
    if not DOMAIN.match(custom_domain):
        raise ConfigError("SMOKE_CUSTOM_DOMAIN must be a host name (no scheme)")
    google_form_id = _required(env, "SMOKE_GOOGLE_FORM_ID")
    if not GOOGLE_FORM_ID.match(google_form_id):
        raise ConfigError("SMOKE_GOOGLE_FORM_ID must be a form's edit id")
    config = Config(
        app_url=app_url,
        api_url=normalize_url(api_url, "--api-url") if api_url else None,
        api_key=api_key,
        workspace=workspace,
        custom_domain=custom_domain,
        google_form_id=google_form_id,
        mailbox=mailbox_settings(env, address, mailpit_url),
        run_tag=tag or run_tag(env),
    )
    # fail early on a malformed base address
    config.run_address
    return config
