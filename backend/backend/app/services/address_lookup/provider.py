"""The client of the address service: one call, two validated values in, one
street and city out.

A free-text address search answers which street and which place a Dutch
postcode and house number belong to. This module is the only place that knows
the service (docs/address-question.md names it for operators):

- the host, the path and the field list are **constants here**: no setting, no
  form and no request chooses where this server connects, so there is no
  address a caller could point it at;
- the query is built from two values that matched strict patterns
  (``postcode_ok`` / ``number_ok``) and constants; nothing else a respondent
  typed reaches it, and :func:`build_query` checks the patterns again;
- the call goes through ``registration.client.request``: https on 443, the host
  resolved at every connection and every answer a public address, the
  connection pinned to the address checked, no redirects, no cookies, no
  compression, a fixed User-Agent, the reply capped, connect/read/total time
  bounded. One attempt: the lookup is on a respondent's request path;
- the reply is untrusted: JSON, ``response.docs`` a list, and a document only
  counts when its postcode and house number are the ones asked for and its
  street and place are clean text (trimmed, in Unicode form C). Several different (street, place) pairs are
  "not found": the lookup never guesses.

Errors are our codes (:class:`LookupUnavailable`), never the service's text, a
status, an address or what was asked. Tests give the service a fake
``Transport``; the real service is never called from a test.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Sequence, Tuple

from common.address import STREET_MAX, CITY_MAX, is_clean_text

from backend.app.services.registration import client

BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
PATH = "free"
USER_AGENT = b"bettercollected-address-lookup/1"
# a lookup that hits returns a handful of small documents
MAX_REPLY_BYTES = 64 * 1024
TIMEOUTS = {"connect": 2.0, "read": 3.0, "write": 2.0, "pool": 2.0}
TOTAL_TIMEOUT_S = 5.0
ROWS = 20
# only these fields come back
FIELDS = "straatnaam,woonplaatsnaam,postcode,huisnummer"

_POSTCODE = re.compile(r"^[1-9][0-9]{3}[A-Z]{2}$")
_NUMBER = re.compile(r"^[1-9][0-9]{0,4}$")

Query = Sequence[Tuple[str, str]]
Transport = Callable[[Query], Awaitable[bytes]]


class LookupUnavailable(Exception):
    """The service could not answer. ``code``: ``timeout``, ``unreachable``,
    ``tls_error``, ``refused`` (a 4xx, a redirect or an address that is not
    public), ``server_error``, ``too_large`` or ``bad_reply``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Place:
    street: str
    city: str


def postcode_ok(value: str) -> bool:
    """``1234AB``: no space, upper case, the letters not SA, SD or SS."""
    return bool(_POSTCODE.fullmatch(value)) and value[4:] not in ("SA", "SD", "SS")


def number_ok(value: str) -> bool:
    """One to five digits, not starting with 0."""
    return bool(_NUMBER.fullmatch(value))


def build_query(postcode: str, number: str) -> List[Tuple[str, str]]:
    """The query pairs for ``postcode`` (``1234AB``) and ``number``. Raises
    ``ValueError`` for anything that is not exactly those two forms."""
    if not postcode_ok(postcode) or not number_ok(number):
        raise ValueError("not a lookup key")
    return [
        ("q", f"postcode:{postcode} and huisnummer:{number}"),
        ("fq", "type:adres"),
        ("fl", FIELDS),
        ("rows", str(ROWS)),
    ]


async def http_transport(query: Query) -> bytes:
    """The real call. Raises :class:`LookupUnavailable`."""
    try:
        reply = await client.request(
            client.Target(base_url=BASE_URL, path=PATH),
            "GET",
            query=list(query),
            keep_reply=True,
            max_reply=MAX_REPLY_BYTES,
            user_agent=USER_AGENT,
            timeouts=TIMEOUTS,
            total_timeout=TOTAL_TIMEOUT_S,
        )
    except client.SendFailed as failed:
        code = failed.code
        if code == "timeout":
            raise LookupUnavailable("timeout")
        if code == "tls_error":
            raise LookupUnavailable("tls_error")
        if code in ("unreachable",):
            raise LookupUnavailable("unreachable")
        if code == "http_5xx":
            raise LookupUnavailable("server_error")
        raise LookupUnavailable("refused")
    if reply.truncated:
        raise LookupUnavailable("too_large")
    return reply.body


def _clean(value: object, limit: int) -> Optional[str]:
    """``value`` trimmed and in Unicode form C when that is clean text of an
    address part, else None (the service's spelling of a place is not ours to
    keep byte for byte: a stored part is always trimmed and in form C)."""
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize("NFC", value.strip())
    return value if is_clean_text(value, limit) else None


def parse_reply(body: bytes, postcode: str, number: str) -> Optional[Place]:
    """The one place the documents agree on, ``None`` when there is none (no
    document, or several different places). Raises ``LookupUnavailable`` when
    the reply is not what the service answers."""
    if not isinstance(body, (bytes, bytearray)) or len(body) > MAX_REPLY_BYTES:
        raise LookupUnavailable("too_large")
    try:
        data = json.loads(bytes(body))
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise LookupUnavailable("bad_reply")
    reply = data.get("response") if isinstance(data, dict) else None
    docs = reply.get("docs") if isinstance(reply, dict) else None
    if not isinstance(docs, list):
        raise LookupUnavailable("bad_reply")
    found = set()
    for doc in docs[: ROWS * 2]:
        if not isinstance(doc, dict):
            continue
        # exactly the address asked for (a fuzzy match is not one)
        if doc.get("postcode") != postcode or str(doc.get("huisnummer")) != number:
            continue
        street = _clean(doc.get("straatnaam"), STREET_MAX)
        city = _clean(doc.get("woonplaatsnaam"), CITY_MAX)
        if street and city:
            found.add((street, city))
    if len(found) != 1:
        return None
    street, city = next(iter(found))
    return Place(street=street, city=city)
