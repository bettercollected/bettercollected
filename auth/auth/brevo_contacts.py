"""Erase the Brevo contacts of accounts deleted before the backend erased them
itself (one-off, run by the operator in the auth container, which reads the
accounts from the store auth reads):

    python -m auth.brevo_contacts                                   # dry run
    python -m auth.brevo_contacts --marker ATTRIBUTE[=VALUE]        # dry run, with the marker
    python -m auth.brevo_contacts --marker ATTRIBUTE[=VALUE] --apply

The key, a Brevo API v3 key (the backend's ``BREVO_CONTACTS_API_KEY``, never
the tracker key), is read from the container's environment
(``BREVO_CONTACTS_API_KEY``); when it is not set there, the command asks for
it without echoing it. It is never taken on the command line, so it stays out
of the shell history.

Lists every Brevo contact (``GET /v3/contacts``, page by page) and looks each
address up among the accounts here, case-insensitively. A contact without an
account belonged to a deleted account, or never had one here: the same Brevo
account may hold contacts from elsewhere (Brevo forms, imports, other
products). The tracker that created this instance's contacts sends only an
address and an event name; it sets no attribute, and Brevo's API does not
list a contact's tracked events. So nothing is deleted on absence alone:

* the dry run prints the breakdown of the contacts without an account
  (with/without the marker, on a list or not, with no attributes at all) and
  the names of the attributes they carry, with counts: counts and attribute
  names only, never an address or a value;
* ``--apply`` needs ``--marker``: an attribute that identifies this
  instance's contacts (``NAME`` = present and not empty, ``NAME=VALUE`` =
  that value, ignoring case), which the owner confirms from the dry run. Only
  contacts without an account, carrying the marker and on **no** Brevo list
  are deleted (a list member may be a newsletter subscriber).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from getpass import getpass
from typing import Awaitable, Callable, List, Optional, Tuple
from urllib.parse import quote

import httpx

BREVO_API_URL = "https://api.brevo.com/v3"
PAGE_SIZE = 500
MAX_ATTEMPTS = 5


class BrevoError(Exception):
    """Brevo refused or failed a request; ``status`` only, never a body."""

    def __init__(self, status: int):
        super().__init__(f"Brevo answered HTTP {status}")
        self.status = status


class BrevoContacts:
    def __init__(
        self,
        api_key: str,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._key = api_key
        self._transport = transport
        self._sleep = sleep

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=BREVO_API_URL,
            transport=self._transport,
            timeout=30,
            headers={"api-key": self._key, "accept": "application/json"},
        ) as client:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                response = await client.request(method, path, **kwargs)
                if response.status_code != 429 or attempt == MAX_ATTEMPTS:
                    return response
                # rate limited: wait and try again
                await self._sleep(2.0 * attempt)
        raise AssertionError("unreachable")

    async def all_contacts(self) -> List[dict]:
        """Every contact: its address, list ids and attributes, kept in
        memory only (never printed)."""
        contacts: List[dict] = []
        offset = 0
        while True:
            response = await self._request(
                "GET", "/contacts", params={"limit": PAGE_SIZE, "offset": offset}
            )
            if response.status_code != 200:
                raise BrevoError(response.status_code)
            page = (response.json() or {}).get("contacts") or []
            for contact in page:
                email = (contact.get("email") or "").strip()
                if email:
                    attributes = contact.get("attributes")
                    contacts.append(
                        {
                            "email": email,
                            "listIds": contact.get("listIds") or [],
                            "attributes": (
                                attributes if isinstance(attributes, dict) else {}
                            ),
                        }
                    )
            if len(page) < PAGE_SIZE:
                return contacts
            offset += PAGE_SIZE

    async def remove_contact(self, email: str) -> str:
        """``deleted``, ``absent`` or ``failed``."""
        response = await self._request(
            "DELETE",
            f"/contacts/{quote(email.lower(), safe='')}",
            params={"identifierType": "email_id"},
        )
        if response.status_code in (200, 204):
            return "deleted"
        if response.status_code == 404:
            return "absent"
        return "failed"


async def _without_account(contacts: List[dict], users) -> List[dict]:
    """The contacts whose address matches no account (ignoring case)."""
    known = set()
    emails = sorted({c["email"].lower() for c in contacts})
    for start in range(0, len(emails), 500):
        batch = emails[start : start + 500]
        for user in await users.get_users_by_emails(batch):
            known.add((user.email or "").lower())
    missing = []
    for contact in contacts:
        email = contact["email"].lower()
        if email in known:
            continue
        # an account stored with other capitals than Brevo's lower-case copy
        if await users.find_users_by_email_ci(email):
            known.add(email)
            continue
        missing.append(contact)
    return missing


def parse_marker(value: Optional[str]) -> Optional[Tuple[str, Optional[str]]]:
    """``NAME`` or ``NAME=VALUE`` as (name, value or None)."""
    if not value or not value.strip():
        return None
    name, sep, expected = value.partition("=")
    name = name.strip()
    if not name:
        raise ValueError("the marker needs an attribute name")
    return name, (expected.strip() if sep else None)


def _present(value) -> bool:
    return value is not None and value is not False and str(value).strip() != ""


def is_marked(contact: dict, marker: Optional[Tuple[str, Optional[str]]]) -> bool:
    if marker is None:
        return False
    name, expected = marker
    attributes = {str(k).casefold(): v for k, v in contact["attributes"].items()}
    value = attributes.get(name.casefold())
    if expected is None:
        return _present(value)
    return _present(value) and str(value).strip().casefold() == expected.casefold()


async def erase(
    brevo: BrevoContacts,
    users,
    apply: bool,
    marker: Optional[Tuple[str, Optional[str]]] = None,
) -> dict:
    if apply and marker is None:
        raise ValueError("--apply needs --marker")
    contacts = await brevo.all_contacts()
    orphans = await _without_account(contacts, users)
    breakdown = Counter(
        ("marked" if is_marked(c, marker) else "unmarked")
        + ("_listed" if c["listIds"] else "_unlisted")
        for c in orphans
    )
    names = Counter(
        str(name)
        for c in orphans
        for name, value in c["attributes"].items()
        if _present(value)
    )
    targets = [c for c in orphans if is_marked(c, marker) and not c["listIds"]]
    counts = {
        "contacts": len(contacts),
        "with_account": len(contacts) - len(orphans),
        "without_account": len(orphans),
        "without_account_by_marker_and_list": {
            key: breakdown.get(key, 0)
            for key in (
                "marked_unlisted",
                "marked_listed",
                "unmarked_unlisted",
                "unmarked_listed",
            )
        },
        "without_account_with_no_attributes": sum(
            1 for c in orphans if not any(_present(v) for v in c["attributes"].values())
        ),
        # attribute names (a schema, not personal data) and how many of the
        # contacts without an account carry each: to choose the marker
        "without_account_attribute_names": dict(sorted(names.items())),
        "marker": None if marker is None else "=".join(p for p in marker if p),
        "to_delete": len(targets),
        "deleted": 0,
        "absent": 0,
        "failed": 0,
    }
    if apply:
        for contact in targets:
            counts[await brevo.remove_contact(contact["email"])] += 1
    return counts


def api_key() -> Optional[str]:
    """From the container's environment, else asked for without echo (never
    an argument: it would stay in the shell history)."""
    key = os.environ.get("BREVO_CONTACTS_API_KEY", "").strip()
    if key:
        return key
    if sys.stdin.isatty():
        return getpass("Brevo API v3 key (not shown): ").strip() or None
    return None


async def _main(args, key: str, marker) -> dict:
    from auth.app.container import container
    from auth.app.services.database_service import close_db, init_db
    from common.db import dispose_engine

    database_client = container.database_client()
    await init_db(database_client, required=container.uses_mongo())
    try:
        return await erase(
            BrevoContacts(key),
            container.user_repository(),
            apply=args.apply,
            marker=marker,
        )
    finally:
        await close_db(database_client)
        await dispose_engine(container.pg_engine())


def main(argv) -> int:
    parser = argparse.ArgumentParser(prog="python -m auth.brevo_contacts")
    parser.add_argument(
        "--apply", action="store_true", help="delete (default: dry run)"
    )
    parser.add_argument(
        "--marker",
        help="ATTRIBUTE or ATTRIBUTE=VALUE identifying this instance's contacts "
        "(needed for --apply)",
    )
    args = parser.parse_args(argv)
    try:
        marker = parse_marker(args.marker)
    except ValueError as error:
        print(f"Stopped: {error}")
        return 2
    if args.apply and marker is None:
        print("Stopped: --apply needs --marker (run the dry run first).")
        return 2
    key = api_key()
    if not key:
        print(
            "Set BREVO_CONTACTS_API_KEY (a Brevo API v3 key) in the container's "
            "environment, or run interactively to be asked for it."
        )
        return 2
    try:
        counts = asyncio.run(_main(args, key, marker))
    except BrevoError as error:
        print(f"Stopped: {error}")
        return 1
    print(json.dumps({"applied": args.apply, **counts}, indent=1, sort_keys=True))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
