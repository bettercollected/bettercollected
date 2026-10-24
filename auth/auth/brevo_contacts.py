"""Erase the Brevo contacts of accounts deleted before the backend erased them
itself (one-off, run by the operator):

    BREVO_CONTACTS_API_KEY=... python -m auth.brevo_contacts                    # dry run
    BREVO_CONTACTS_API_KEY=... python -m auth.brevo_contacts --apply
    BREVO_CONTACTS_API_KEY=... python -m auth.brevo_contacts --apply --include-listed

Runs in the auth container (it reads the accounts from the store auth reads).
Lists every Brevo contact (``GET /v3/contacts``, page by page) and looks each
address up among the accounts here, case-insensitively. A contact with no
account belonged to a deleted account, or never had one: a contact that is on
one of your Brevo lists (``listIds``) may be a newsletter subscriber from
elsewhere, so only contacts on **no** list are deleted, unless
``--include-listed``. Without ``--apply`` nothing changes.

Prints counts only, never an address. The key is a Brevo API v3 key (the
backend's ``BREVO_CONTACTS_API_KEY``), never the tracker key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Awaitable, Callable, Dict, List, Optional
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
        """Every contact (email and list ids only are kept)."""
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
                    contacts.append(
                        {"email": email, "listIds": contact.get("listIds") or []}
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


async def erase(
    brevo: BrevoContacts, users, apply: bool, include_listed: bool
) -> Dict[str, int]:
    contacts = await brevo.all_contacts()
    orphans = await _without_account(contacts, users)
    unlisted = [c for c in orphans if not c["listIds"]]
    targets = orphans if include_listed else unlisted
    counts = {
        "contacts": len(contacts),
        "with_account": len(contacts) - len(orphans),
        "without_account": len(orphans),
        "without_account_on_no_list": len(unlisted),
        "without_account_on_a_list": len(orphans) - len(unlisted),
        "to_delete": len(targets),
        "deleted": 0,
        "absent": 0,
        "failed": 0,
    }
    if apply:
        for contact in targets:
            counts[await brevo.remove_contact(contact["email"])] += 1
    return counts


async def _main(args) -> Dict[str, int]:
    from auth.app.container import container
    from auth.app.services.database_service import close_db, init_db
    from common.db import dispose_engine

    database_client = container.database_client()
    await init_db(database_client, required=container.uses_mongo())
    try:
        return await erase(
            BrevoContacts(os.environ["BREVO_CONTACTS_API_KEY"]),
            container.user_repository(),
            apply=args.apply,
            include_listed=args.include_listed,
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
        "--include-listed",
        action="store_true",
        help="also delete contacts without an account that are on a Brevo list",
    )
    args = parser.parse_args(argv)
    if not os.environ.get("BREVO_CONTACTS_API_KEY"):
        print("Set BREVO_CONTACTS_API_KEY (a Brevo API v3 key) in the environment.")
        return 2
    try:
        counts = asyncio.run(_main(args))
    except BrevoError as error:
        print(f"Stopped: {error}")
        return 1
    print(json.dumps({"applied": args.apply, **counts}, indent=1, sort_keys=True))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
