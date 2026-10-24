"""The test mailbox: IMAP (app password), the Gmail API (gmail.readonly) or,
for a local dry run, a Mailpit inbox.

Every reader looks only at mails addressed to this run's plus-address and
never changes any other mail. After reading, the run's own mails are deleted
where the access allows it (IMAP: moved to the bin; Mailpit: deleted); the
Gmail API with ``gmail.readonly`` cannot delete, so they stay.
"""

from __future__ import annotations

import base64
import datetime as dt
import imaplib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, List, Optional

from smoke.config import GMAIL_API, IMAP, MAILPIT, MailboxSettings
from smoke.mail import (
    MailMessage,
    extract_code,
    is_for,
    newest_code_mail,
    parse_message,
)
from smoke.redact import Redactor

USER_AGENT = "bettercollected-smoke/1"
POLL_SECONDS = 5
WAIT_SECONDS = 180


class MailboxError(Exception):
    pass


def _quote_imap(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9.+_@-]+", value):
        raise MailboxError("refusing an unexpected character in an IMAP search")
    return f'"{value}"'


class Mailbox:
    """Base: the polling and the code extraction; subclasses fetch."""

    deletes = False

    def __init__(self, settings: MailboxSettings, redactor: Redactor) -> None:
        self.settings = settings
        self.redactor = redactor
        self.read_ids: set[str] = set()

    # -- for subclasses -----------------------------------------------------
    def fetch(self, address: str, since: dt.datetime) -> List[MailMessage]:
        raise NotImplementedError

    def delete(self, address: str) -> int:
        return 0

    def close(self) -> None:
        pass

    # -- shared --------------------------------------------------------------
    def wait_for_code(
        self,
        address: str,
        not_before: dt.datetime,
        timeout: float = WAIT_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> str:
        """Poll until the newest code mail to ``address`` arrives; the code is
        registered with the redactor before it is returned."""
        deadline = clock() + timeout
        while True:
            messages = [
                m for m in self.fetch(address, not_before) if is_for(m, address)
            ]
            newest = newest_code_mail(messages, address, not_before)
            if newest is not None:
                self.read_ids.update(m.id for m in messages)
                code = extract_code(newest)
                self.redactor.add(code)
                return code
            if clock() >= deadline:
                raise MailboxError(
                    f"no code mail to the run's address within {int(timeout)} s"
                )
            sleep(POLL_SECONDS)

    def cleanup(self, address: str) -> str:
        if not self.deletes:
            return "code mail left in the mailbox (read-only access)"
        try:
            count = self.delete(address)
        except Exception as error:  # reported, never fails the run
            return f"could not delete the run's mail ({type(error).__name__})"
        return f"deleted {count} mail(s) to the run's address"


class ImapMailbox(Mailbox):
    deletes = True

    def __init__(self, settings: MailboxSettings, redactor: Redactor) -> None:
        super().__init__(settings, redactor)
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        if self._imap is None:
            imap = imaplib.IMAP4_SSL(self.settings.imap_host, 993, timeout=30)
            try:
                imap.login(self.settings.address, self.settings.app_password)
            except imaplib.IMAP4.error:
                raise MailboxError("IMAP sign-in refused (check the app password)")
            imap.select("INBOX")
            self._imap = imap
        return self._imap

    def _search(self, address: str, since: dt.datetime) -> List[bytes]:
        imap = self._connect()
        imap.noop()  # see mail that arrived since the last poll
        day = since.astimezone(dt.timezone.utc) - dt.timedelta(days=1)
        status, data = imap.uid(
            "SEARCH",
            None,
            "TO",
            _quote_imap(address),
            "SINCE",
            day.strftime("%d-%b-%Y"),
        )
        if status != "OK":
            raise MailboxError("IMAP search failed")
        return data[0].split() if data and data[0] else []

    def fetch(self, address: str, since: dt.datetime) -> List[MailMessage]:
        imap = self._connect()
        messages = []
        for uid in self._search(address, since)[-10:]:
            # BODY.PEEK: reading does not mark the mail as read
            status, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                continue
            messages.append(parse_message(uid.decode(), data[0][1]))
        return messages

    def _trash(self) -> Optional[str]:
        status, folders = self._connect().list()
        for line in folders or []:
            text = (
                line.decode(errors="replace") if isinstance(line, bytes) else str(line)
            )
            if "\\Trash" in text:
                match = re.search(r'"([^"]+)"\s*$', text) or re.search(
                    r"(\S+)\s*$", text
                )
                if match:
                    return match.group(1)
        return None

    def delete(self, address: str) -> int:
        imap = self._connect()
        # only this run's mails: the same search the reader used
        uids = self._search(address, dt.datetime.now(dt.timezone.utc))
        if not uids:
            return 0
        uid_set = b",".join(uids).decode()
        trash = self._trash()
        if trash:
            status, _ = imap.uid("MOVE", uid_set, f'"{trash}"')
            if status == "OK":
                return len(uids)
        imap.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")
        imap.expunge()
        return len(uids)

    def close(self) -> None:
        if self._imap is not None:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None


def _http_json(
    url: str,
    *,
    data: Optional[bytes] = None,
    headers: Optional[dict] = None,
    method: Optional[str] = None,
    timeout: float = 30,
) -> object:
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else None


class GmailApiMailbox(Mailbox):
    """gmail.readonly: lists and reads; cannot delete."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, settings: MailboxSettings, redactor: Redactor) -> None:
        super().__init__(settings, redactor)
        self._token: Optional[str] = None

    def _access_token(self) -> str:
        if self._token is None:
            form = urllib.parse.urlencode(
                {
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                    "refresh_token": self.settings.refresh_token,
                    "grant_type": "refresh_token",
                }
            ).encode()
            try:
                body = _http_json(
                    self.TOKEN_URL,
                    data=form,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
            except urllib.error.HTTPError as error:
                raise MailboxError(
                    f"Gmail token refresh refused (HTTP {error.code}); the "
                    "refresh token may have expired"
                )
            token = (body or {}).get("access_token") if isinstance(body, dict) else None
            if not token:
                raise MailboxError("Gmail token refresh gave no access token")
            self.redactor.add(token)
            self._token = token
        return self._token

    def fetch(self, address: str, since: dt.datetime) -> List[MailMessage]:
        auth = {"Authorization": f"Bearer {self._access_token()}"}
        after = int((since - dt.timedelta(days=1)).timestamp())
        query = urllib.parse.urlencode(
            {"q": f"to:{address} after:{after}", "maxResults": "10"}
        )
        listing = _http_json(f"{self.API}/messages?{query}", headers=auth) or {}
        messages = []
        for item in listing.get("messages", []) if isinstance(listing, dict) else []:
            message_id = str(item.get("id", ""))
            if not re.fullmatch(r"[A-Za-z0-9]{1,64}", message_id):
                continue
            body = _http_json(
                f"{self.API}/messages/{message_id}?format=raw", headers=auth
            )
            raw = (body or {}).get("raw") if isinstance(body, dict) else None
            if raw:
                messages.append(
                    parse_message(message_id, base64.urlsafe_b64decode(raw + "=="))
                )
        return messages


class MailpitMailbox(Mailbox):
    """A local Mailpit inbox (dry runs only)."""

    deletes = True

    def fetch(self, address: str, since: dt.datetime) -> List[MailMessage]:
        base = self.settings.mailpit_url
        query = urllib.parse.urlencode({"query": f'to:"{address}"', "limit": "10"})
        listing = _http_json(f"{base}/api/v1/search?{query}") or {}
        messages = []
        for item in listing.get("messages", []) if isinstance(listing, dict) else []:
            message_id = str(item.get("ID", ""))
            if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", message_id):
                continue
            request = urllib.request.Request(
                f"{base}/api/v1/message/{message_id}/raw",
                headers={"User-Agent": USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                messages.append(parse_message(message_id, response.read()))
        return messages

    def delete(self, address: str) -> int:
        ids = [
            m.id
            for m in self.fetch(address, dt.datetime.now(dt.timezone.utc))
            if is_for(m, address)
        ]
        if ids:
            request = urllib.request.Request(
                f"{self.settings.mailpit_url}/api/v1/messages",
                data=json.dumps({"IDs": ids}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="DELETE",
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                response.read()
        return len(ids)


def open_mailbox(settings: MailboxSettings, redactor: Redactor) -> Mailbox:
    kinds = {IMAP: ImapMailbox, GMAIL_API: GmailApiMailbox, MAILPIT: MailpitMailbox}
    return kinds[settings.kind](settings, redactor)
