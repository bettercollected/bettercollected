"""Accounts whose emails differ only in case: which to keep, which to drop.

Read by the admin task ``auth.resolve_case_duplicate_accounts`` through the
internal routes in ``controllers/admin_tasks_router.py``
(docs/postgres-cutover-runbook.md, "Accounts whose emails differ only in
case"). For each group of accounts whose emails are equal ignoring case:

1. an account without forms is dropped;
2. if exactly one account has forms, it is kept;
3. if none has forms, the one created last is kept (the ObjectId's timestamp,
   since some documents have no ``created_at``; equal timestamps: the larger
   id), and the others are dropped;
4. if two or more have forms, those are left for manual handling; the
   formless ones in the group are still dropped (rule 1).

"Has forms": the account's deletion would take at least one form, that is a
``workspace_forms`` row in a workspace it owns (``workspaces.owner_id``) or one
it imported (``workspace_forms.user_id``); distinct form ids are counted.

A drop goes through the product's account deletion, the same path as a
user's own request (``AuthService.add_workflow_to_delete_user``): sessions
revoked, then the deletion job removes the workspaces, forms, memberships,
integration credentials, the auth account and its billing customer, in every
store the services write. Every drop re-evaluates the account's group first.

Ids only: no email leaves this module (the auth service groups the accounts
and returns ids; the one email a deletion needs is read by id and handed to
the deletion path, as for the user's own request).

A failing call to the auth service raises :class:`AuthCallFailed` with a
stable code (``auth_unreachable``, ``auth_misconfigured``, ``auth_refused``,
``auth_error``) and auth's status, never its body; a deletion that cannot be
started (the deletion workflow, Temporal, the jobs worker) raises
:class:`DeletionUnavailable`. The routes answer 502 with the code and status,
so the runner can tell these from the API's own 503 (its admin task key is
unset) and 403 (another key).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Dict, List, Optional, Sequence

import httpx
from bson import ObjectId
from common.models.user import User
from loguru import logger

from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

KEEP = "keep"
DROP = "drop"
MANUAL = "manual"

AUTH_UNREACHABLE = "auth_unreachable"
AUTH_MISCONFIGURED = "auth_misconfigured"
AUTH_REFUSED = "auth_refused"
AUTH_ERROR = "auth_error"
DELETION_UNAVAILABLE = "deletion_unavailable"


class UpstreamFailed(Exception):
    """Something the route depends on failed: ``code`` says what, ``status``
    is the HTTP status it reported (None when there was none). Answered as
    502 by the routes, never with a body or message of the failure."""

    def __init__(self, code: str, status: Optional[int] = None):
        super().__init__(code)
        self.code = code
        self.status = status


class AuthCallFailed(UpstreamFailed):
    """A call to the auth service failed."""


class DeletionUnavailable(UpstreamFailed):
    """The account deletion could not be started."""

    def __init__(self, status: Optional[int] = None):
        super().__init__(DELETION_UNAVAILABLE, status)


def _auth_reply(reply: httpx.Response) -> dict:
    status = reply.status_code
    if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        # the backend's AUTH_INTERNAL_NOTIFY_KEY is not the one auth holds
        raise AuthCallFailed(AUTH_REFUSED, status)
    if status != HTTPStatus.OK:
        raise AuthCallFailed(AUTH_ERROR, status)
    try:
        body = reply.json()
    except ValueError:
        raise AuthCallFailed(AUTH_ERROR, status) from None
    if not isinstance(body, dict):
        raise AuthCallFailed(AUTH_ERROR, status)
    return body


@dataclass(frozen=True)
class Account:
    id: str
    created_at: datetime
    forms: int
    decision: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "forms": self.forms,
            "decision": self.decision,
        }


def created_at(user_id: str) -> datetime:
    """When the account was created: its ObjectId's timestamp (UTC)."""
    return ObjectId(user_id).generation_time.astimezone(timezone.utc)


def decide(forms: Dict[str, int]) -> Dict[str, str]:
    """``{account id: forms count}`` of one group -> ``{id: decision}``."""
    with_forms = [i for i, n in forms.items() if n > 0]
    if len(with_forms) >= 2:
        return {i: MANUAL if forms[i] > 0 else DROP for i in forms}
    if len(with_forms) == 1:
        keeper = with_forms[0]
    else:
        keeper = max(forms, key=lambda i: (created_at(i), ObjectId(i)))
    return {i: KEEP if i == keeper else DROP for i in forms}


class CaseDuplicateAccounts:
    def __init__(self, http_client, workspace_repo, workspace_form_repo, auth_service):
        self._http = http_client
        self._workspaces = workspace_repo
        self._workspace_forms = workspace_form_repo
        self._auth_service = auth_service

    async def _auth_get(self, path: str, **kwargs) -> dict:
        """GET from the auth service; any failure is an :class:`AuthCallFailed`
        (the raw request, not ``HttpClient.get``, which would pass auth's
        status through as the backend's own)."""
        try:
            reply = await self._http.request(
                "GET",
                settings.auth_settings.BASE_URL + path,
                headers=auth_service_headers(),
                **kwargs,
            )
        except (httpx.InvalidURL, httpx.UnsupportedProtocol):
            # AUTH_BASE_URL is not a usable URL (InvalidURL is not an
            # httpx.HTTPError)
            raise AuthCallFailed(AUTH_MISCONFIGURED) from None
        except httpx.TransportError:
            raise AuthCallFailed(AUTH_UNREACHABLE) from None
        except httpx.HTTPError:
            raise AuthCallFailed(AUTH_ERROR) from None
        return _auth_reply(reply)

    async def _group_ids(self) -> List[List[str]]:
        reply = await self._auth_get("/users/case-duplicates", timeout=60)
        groups = reply.get("groups") or []
        return [[str(i) for i in group] for group in groups if len(group) > 1]

    async def forms_of(self, user_id: str) -> int:
        workspaces = await self._workspaces.get_user_workspaces(user_id)
        return await self._workspace_forms.count_forms_of_account(
            [workspace.id for workspace in workspaces], user_id
        )

    async def _evaluate(self, ids: Sequence[str]) -> List[Account]:
        forms = {i: await self.forms_of(i) for i in ids}
        decisions = decide(forms)
        return [Account(i, created_at(i), forms[i], decisions[i]) for i in ids]

    async def plan(self) -> List[List[Account]]:
        """Every group, in a stable order (by its smallest id)."""
        return [await self._evaluate(ids) for ids in sorted(await self._group_ids())]

    async def _email_of(self, user_id: str) -> Optional[str]:
        reply = await self._auth_get(
            "/users", params={"user_ids": [user_id]}, timeout=30
        )
        for user in reply.get("users_info") or []:
            if str(user.get("_id") or user.get("id")) == user_id:
                return user.get("email")
        return None

    async def drop(self, user_id: str) -> str:
        """Drop one account if, evaluated now, its group still drops it.

        Returns ``queued`` (the deletion was started), ``already_queued`` (a
        deletion of it is already running), ``not_found`` (no longer in a
        group of case variants), ``kept`` / ``manual`` (the rules no longer
        drop it), or ``refused`` (the account deletion itself refused, e.g.
        the account is the billing owner of a workspace with other owners)."""
        group = next((g for g in await self._group_ids() if user_id in g), None)
        if group is None:
            return "not_found"
        account = next(a for a in await self._evaluate(group) if a.id == user_id)
        if account.decision == KEEP:
            return "kept"
        if account.decision == MANUAL:
            return "manual"
        email = await self._email_of(user_id)
        if not email:
            return "not_found"
        try:
            started = await self._auth_service.add_workflow_to_delete_user(
                User(id=user_id, sub=email)
            )
        except Exception as error:
            status = getattr(error, "status_code", None)
            if status == HTTPStatus.CONFLICT:
                # the product's own refusal (billing owner of a shared workspace)
                return "refused"
            # not started: Temporal, the jobs worker or the event log failed.
            # The type only: a message could name the account.
            logger.warning(
                "Case-duplicate account deletion could not be started ({}, status {}).",
                type(error).__name__,
                status,
            )
            raise DeletionUnavailable(status if isinstance(status, int) else None) from None
        logger.info("Case-duplicate account {} queued for deletion.", user_id)
        return "queued" if started else "already_queued"
