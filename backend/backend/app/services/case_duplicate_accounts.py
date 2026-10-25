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

While a Mongo store is configured for the backend, both routes refuse with
409 and code ``forms_import_incomplete`` until the 4.0 forms import is
complete (``backend.db.forms_import``): the forms are counted in Postgres
only, and before the import every account would count none, so the newest
of each group would be kept and the others dropped.

Ids only: no email leaves this module (the auth service groups the accounts
and returns ids; the one email a deletion needs is read by id and handed to
the deletion path, as for the user's own request).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Dict, List, Optional, Sequence

from bson import ObjectId
from common.models.user import User
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.db.forms_import import CODE as FORMS_IMPORT_INCOMPLETE
from backend.db.forms_import import import_problem
from backend.app.services.internal_auth import auth_service_headers
from backend.config import settings

KEEP = "keep"
DROP = "drop"
MANUAL = "manual"


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


def backend_mongo_database():
    """The backend's Mongo database, opened as the startup import guard opens
    it (``mongo_import_guard._database``): the container's client while a
    group uses Mongo, else a client of its own while ``MONGO_URI`` is
    configured (set, not just the built-in default). An async context
    yielding None when neither: no Mongo, nothing to check."""
    from backend.app.container import container
    from backend.db.mongo_import_guard import _database, mongo_uri_configured
    from backend.db.startup import mongo_required

    return _database(
        container.database_client() if mongo_required(container) else None,
        mongo_uri_configured(settings.mongo_settings),
        settings.mongo_settings.DB,
    )


def backend_postgres_engine():
    from backend.app.container import container

    return container.pg_engine()


class CaseDuplicateAccounts:
    def __init__(
        self,
        http_client,
        workspace_repo,
        workspace_form_repo,
        auth_service,
        mongo_database=backend_mongo_database,
        postgres_engine=backend_postgres_engine,
    ):
        self._http = http_client
        self._workspaces = workspace_repo
        self._workspace_forms = workspace_form_repo
        self._auth_service = auth_service
        self._mongo_database = mongo_database
        self._postgres_engine = postgres_engine

    async def ensure_forms_imported(self) -> None:
        """409 ``forms_import_incomplete`` until the forms import is complete
        (``backend.db.forms_import``: a finished backfill recorded, or every
        link of Mongo's 4.0 copy in Postgres), or while a configured Mongo
        cannot be read. Without Mongo configured there is nothing to check."""
        async with self._mongo_database() as database:
            if database is None:
                return
            problem = await import_problem(
                database,
                await self._workspace_forms.links_by_form(),
                self._postgres_engine(),
            )
        if problem is None:
            return
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            content={"code": FORMS_IMPORT_INCOMPLETE, "message": problem[1]},
        )

    async def _group_ids(self) -> List[List[str]]:
        reply = await self._http.get(
            settings.auth_settings.BASE_URL + "/users/case-duplicates",
            headers=auth_service_headers(),
            timeout=60,
        )
        groups = (reply or {}).get("groups") or []
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
        await self.ensure_forms_imported()
        return [await self._evaluate(ids) for ids in sorted(await self._group_ids())]

    async def _email_of(self, user_id: str) -> Optional[str]:
        reply = await self._http.get(
            settings.auth_settings.BASE_URL + "/users",
            params={"user_ids": [user_id]},
            headers=auth_service_headers(),
        )
        for user in (reply or {}).get("users_info") or []:
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
        await self.ensure_forms_imported()
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
        except HTTPException as error:
            if error.status_code == HTTPStatus.CONFLICT:
                return "refused"
            raise
        logger.info("Case-duplicate account {} queued for deletion.", user_id)
        return "queued" if started else "already_queued"
