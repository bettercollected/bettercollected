"""Find and delete the forms that belong to no workspace. The core of the
``responses.purge_orphaned_forms`` task.

A form is an orphan when, in every configured store, no workspace link names it
and none of its responses carries a workspace, and it has at least one response
(a form that is being created has no link for a moment, and no responses yet:
a form without responses is never in scope). ``newest_response_before`` narrows
that to the forms whose newest response was stored before a date; the date is
the one in the response's id (Postgres keeps the Mongo ``_id``, so both stores
agree on it).

Deleting a form removes, in each store: its responder-group links, its
versions, its responses' deletion requests, the form document, then its
responses (last: a form whose deletion stopped half way still has responses,
so it is found again). Files in object storage are not touched: their folder is
named after the workspace, which is unknown.

Only counts and ids leave this module, never titles or answers.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set

from backend.admin.tasks.impl.responses_common import MongoBase, PostgresBase

# what a purge deletes, in the order it deletes it (responses last)
KINDS = ("group_links", "versions", "deletion_requests", "forms", "responses")


@dataclass(frozen=True)
class FormStats:
    """One form's responses in one store."""

    responses: int
    stamped: int
    oldest: Optional[str]  # the oldest response id (24 hex)
    newest: Optional[str]


def id_time(key: Optional[str]) -> Optional[dt.datetime]:
    """When a record with this id (an ObjectId's hex) was stored, or None."""
    if not key or len(key) != 24:
        return None
    try:
        return dt.datetime.fromtimestamp(int(key[:8], 16), tz=dt.timezone.utc)
    except ValueError:
        return None


# --------------------------------------------------------------------- stores
class MongoPurgeStore(MongoBase):
    COLLECTIONS = {
        "responses": "form_responses",
        "deletion_requests": "responses_deletion_requests",
        "versions": "form_versions",
        "group_links": "responder_group_form",
        "forms": "forms",
    }

    @staticmethod
    def _values(form_ids: Iterable[str]) -> list:
        """The form ids as stored: strings, and ObjectIds where an older
        document kept one."""
        from bson import ObjectId

        ids = [str(f) for f in form_ids]
        return ids + [ObjectId(f) for f in ids if ObjectId.is_valid(f) and len(f) == 24]

    async def linked_forms(self, form_ids: Optional[Sequence[str]] = None) -> Set[str]:
        query = {} if form_ids is None else {"form_id": {"$in": self._values(form_ids)}}
        cursor = self.db["workspace_forms"].find(query, {"form_id": 1})
        return {str(row["form_id"]) async for row in cursor if row.get("form_id") is not None}

    async def response_stats(
        self, form_ids: Optional[Sequence[str]] = None
    ) -> Dict[str, FormStats]:
        pipeline: list = []
        if form_ids is not None:
            pipeline.append({"$match": {"form_id": {"$in": self._values(form_ids)}}})
        pipeline.append(
            {
                "$group": {
                    "_id": "$form_id",
                    "n": {"$sum": 1},
                    "stamped": {
                        "$sum": {"$cond": [{"$ifNull": ["$workspace_id", False]}, 1, 0]}
                    },
                    "oldest": {"$min": "$_id"},
                    "newest": {"$max": "$_id"},
                }
            }
        )
        cursor = await self.db["form_responses"].aggregate(pipeline, allowDiskUse=True)
        out: Dict[str, FormStats] = {}
        async for row in cursor:
            if row["_id"] is None:
                continue
            form_id = str(row["_id"])
            previous = out.get(form_id)  # a str and an ObjectId copy of one id
            stats = FormStats(row["n"], row["stamped"], str(row["oldest"]), str(row["newest"]))
            out[form_id] = stats if previous is None else _merge(previous, stats)
        return out

    async def count(self, form_ids: Sequence[str]) -> Dict[str, int]:
        query = {"form_id": {"$in": self._values(form_ids)}}
        return {
            kind: await self.db[self.COLLECTIONS[kind]].count_documents(query)
            for kind in KINDS
        }

    async def delete(self, form_ids: Sequence[str]) -> Dict[str, int]:
        query = {"form_id": {"$in": self._values(form_ids)}}
        out: Dict[str, int] = {}
        for kind in KINDS:
            result = await self.db[self.COLLECTIONS[kind]].delete_many(query)
            out[kind] = result.deleted_count
        return out


class PostgresPurgeStore(PostgresBase):
    @staticmethod
    def _rows():
        from backend.db.models import (
            FormResponseRow,
            FormRow,
            FormVersionRow,
            ResponderGroupFormRow,
            ResponseDeletionRequestRow,
        )

        return {
            "responses": FormResponseRow,
            "deletion_requests": ResponseDeletionRequestRow,
            "versions": FormVersionRow,
            "group_links": ResponderGroupFormRow,
            "forms": FormRow,
        }

    async def linked_forms(self, form_ids: Optional[Sequence[str]] = None) -> Set[str]:
        from sqlalchemy import select

        from backend.db.models import WorkspaceFormRow as w

        stmt = select(w.form_id).distinct()
        if form_ids is not None:
            stmt = stmt.where(w.form_id.in_([str(f) for f in form_ids]))
        async with self.engine.connect() as conn:
            return {str(f) for (f,) in await conn.execute(stmt) if f is not None}

    async def response_stats(
        self, form_ids: Optional[Sequence[str]] = None
    ) -> Dict[str, FormStats]:
        from sqlalchemy import func, select

        from backend.db.models import FormResponseRow as r

        stmt = select(
            r.form_id,
            func.count(),
            func.count(r.workspace_id),
            func.min(r.id),
            func.max(r.id),
        ).group_by(r.form_id)
        if form_ids is not None:
            stmt = stmt.where(r.form_id.in_([str(f) for f in form_ids]))
        async with self.engine.connect() as conn:
            return {
                str(form_id): FormStats(n, stamped, oldest, newest)
                for form_id, n, stamped, oldest, newest in await conn.execute(stmt)
                if form_id is not None
            }

    async def count(self, form_ids: Sequence[str]) -> Dict[str, int]:
        from sqlalchemy import func, select

        ids = [str(f) for f in form_ids]
        out: Dict[str, int] = {}
        async with self.engine.connect() as conn:
            for kind in KINDS:
                row = self._rows()[kind]
                out[kind] = (
                    await conn.execute(
                        select(func.count()).select_from(row).where(row.form_id.in_(ids))
                    )
                ).scalar_one()
        return out

    async def delete(self, form_ids: Sequence[str]) -> Dict[str, int]:
        """One transaction: all of the batch's records in this store, or none."""
        from sqlalchemy import delete

        ids = [str(f) for f in form_ids]
        out: Dict[str, int] = {}
        async with self.engine.begin() as conn:
            for kind in KINDS:
                row = self._rows()[kind]
                result = await conn.execute(delete(row).where(row.form_id.in_(ids)))
                out[kind] = result.rowcount or 0
        return out


STORE_CLASSES = {"mongo": MongoPurgeStore, "postgres": PostgresPurgeStore}


# ----------------------------------------------------------------------- plan
def _merge(a: FormStats, b: FormStats) -> FormStats:
    """One form's stats from two groups (its id stored as a string in some
    responses and as an ObjectId in others). Ids of one length and case
    compare as their dates do."""
    olds = [v for v in (a.oldest, b.oldest) if v]
    news = [v for v in (a.newest, b.newest) if v]
    return FormStats(
        a.responses + b.responses,
        a.stamped + b.stamped,
        min(olds) if olds else None,
        max(news) if news else None,
    )


@dataclass
class Plan:
    """The forms in scope (sorted) and what the run found about them."""

    forms: List[str] = field(default_factory=list)
    # form -> responses, per store covered
    responses: Dict[str, Dict[str, int]] = field(default_factory=dict)
    skipped_stamped: int = 0
    skipped_newer: int = 0
    oldest: Optional[dt.datetime] = None
    newest: Optional[dt.datetime] = None

    def store_responses(self, store: str, forms: Optional[Iterable[str]] = None) -> int:
        counts = self.responses.get(store, {})
        return sum(counts.get(f, 0) for f in (self.forms if forms is None else forms))

    def stores_agree(self, forms: Optional[Iterable[str]] = None) -> bool:
        """Whether every covered store holds as many responses of each form."""
        stores = list(self.responses)
        return all(
            self.responses[s].get(f, 0) == self.responses[stores[0]].get(f, 0)
            for f in (self.forms if forms is None else forms)
            for s in stores[1:]
        )


def plan_orphans(
    linked: Set[str],
    stats: Mapping[str, Mapping[str, FormStats]],
    targets: Sequence[str],
    newest_before: Optional[dt.date] = None,
) -> Plan:
    """The forms in scope. ``linked``: the forms any configured store links to a
    workspace. ``stats``: per configured store, each form's responses.
    ``targets``: the stores the run covers (the candidates are the forms with
    responses there)."""
    cutoff = (
        dt.datetime.combine(newest_before, dt.time.min, tzinfo=dt.timezone.utc)
        if newest_before is not None
        else None
    )
    candidates = sorted({f for t in targets for f in stats.get(t, {})} - linked)
    plan = Plan(responses={t: {} for t in targets})
    for form in candidates:
        if any(stats[s][form].stamped for s in stats if form in stats[s]):
            plan.skipped_stamped += 1
            continue
        times_new = [id_time(stats[t][form].newest) for t in targets if form in stats[t]]
        times_old = [id_time(stats[t][form].oldest) for t in targets if form in stats[t]]
        if cutoff is not None:
            # an id without a readable date is never taken to be old enough
            if any(t is None for t in times_new) or max(times_new) >= cutoff:
                plan.skipped_newer += 1
                continue
        plan.forms.append(form)
        for t in targets:
            if form in stats[t]:
                plan.responses[t][form] = stats[t][form].responses
        known_old = [t for t in times_old if t is not None]
        known_new = [t for t in times_new if t is not None]
        if known_old:
            plan.oldest = min([*known_old, *([plan.oldest] if plan.oldest else [])])
        if known_new:
            plan.newest = max([*known_new, *([plan.newest] if plan.newest else [])])
    return plan


async def find_orphans(
    stores: Sequence, targets: Sequence[str], newest_before: Optional[dt.date] = None
) -> Plan:
    """:func:`plan_orphans` over the open ``stores`` (every configured one)."""
    linked: Set[str] = set()
    stats: Dict[str, Dict[str, FormStats]] = {}
    for store in stores:
        linked |= await store.linked_forms()
        stats[store.name] = await store.response_stats()
    return plan_orphans(linked, stats, targets, newest_before)


async def still_orphans(stores: Sequence, forms: Sequence[str]) -> List[str]:
    """Of ``forms``, those that are still in no workspace and have no stamped
    response in any of the ``stores``, just before they are deleted."""
    changed: Set[str] = set()
    for store in stores:
        changed |= await store.linked_forms(forms)
        changed |= {f for f, s in (await store.response_stats(forms)).items() if s.stamped}
    return [f for f in forms if f not in changed]
