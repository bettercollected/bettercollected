"""Stamp stored responses with the workspace they belong to. The core of the
``responses.backfill_workspaces`` task and of
``scripts/backfill_response_workspaces.py``.

Responses (``form_responses``) and deletion requests
(``responses_deletion_requests``) stored before ``workspace_id`` existed carry
none. Each one is attributed as follows:

* the form is linked to exactly one workspace -> that workspace;
* the form is linked to several workspaces -> the workspace whose key context
  opens the stored ciphertext. ``answers`` (else ``hidden_fields``, else
  ``internal_answers``) are encrypted with an AEAD whose associated data is
  ``workspace_id|form_id``, so exactly one candidate workspace authenticates
  it: the one whose import or submission stored it. Needs the keyset. The
  plaintext is discarded unread;
* nothing to authenticate (no answers, plaintext answers, key unavailable) on a
  form linked to several workspaces -> ambiguous: left unstamped, so it stays
  hidden from every workspace. There is deliberately no option to guess: an
  ambiguous record may be any of the workspaces' respondents' data. While a
  form has such records it cannot be unlinked from one of its workspaces
  (409), so they never pass to the remaining one;
* the form is linked to no workspace -> orphaned, left alone.

A deletion request takes its response's workspace (as stamped, or as this run
attributes it), else the same rules by its form.

Reports counts per store and bucket, never ids, answers or identities. Applying
only ever sets ``workspace_id`` where it is missing, so it is idempotent and
resumes by skipping what is already stamped (and, in the task, by an id cursor).
"""

from __future__ import annotations

from collections import Counter
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

from backend.admin.tasks.impl.responses_common import (
    CIPHERTEXT_PREFIX,
    Opener,
    PostgresBase,
    load_keyset,
    make_opener,
)

ENCRYPTED_FIELDS = ("answers", "hidden_fields", "internal_answers")
PHASES = ("form_responses", "responses_deletion_requests")


class StampConflict(Exception):
    """The record cannot take the workspace: a copy of it (same provider
    response id) is already stamped with it (unique index). Skipped, counted."""


# called after each batch with (phase, last key of the batch, unstamped records
# seen so far in the store); True stops the run (cancel)
OnBatch = Callable[[str, Any, int], Awaitable[bool]]


# --------------------------------------------------------------- attribution
def _ciphertext(record: Dict[str, Any]) -> Optional[bytes]:
    for field in ENCRYPTED_FIELDS:
        value = record.get(field)
        if isinstance(value, (bytes, bytearray)) and bytes(value).startswith(
            CIPHERTEXT_PREFIX
        ):
            return bytes(value)
    return None


def default_opener() -> Optional[Opener]:
    """``opens(workspace_id, form_id, ciphertext)``, or None without a key."""
    keyset = load_keyset()
    if keyset is None:
        return None
    return make_opener(keyset, lenient=True)


class Attributor:
    """Decides the workspace of one record from the form's links."""

    def __init__(self, links: Dict[str, List[str]], opens: Optional[Opener]):
        # form_id -> workspace ids, first linked first
        self.links = links
        self.opens = opens

    def by_form(self, form_id: str) -> Tuple[str, Optional[str]]:
        workspaces = self.links.get(str(form_id)) or []
        if not workspaces:
            return "orphaned", None
        if len(workspaces) == 1:
            return "single_workspace", workspaces[0]
        return "ambiguous", None

    def response(self, record: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        form_id = str(record.get("form_id"))
        workspaces = self.links.get(form_id) or []
        if len(workspaces) > 1:
            ciphertext = _ciphertext(record)
            if ciphertext is not None and self.opens is not None:
                matches = [w for w in workspaces if self.opens(w, form_id, ciphertext)]
                if len(matches) == 1:
                    return "attributed_by_encryption", matches[0]
        return self.by_form(form_id)


def allowed_forms(
    links: Dict[str, List[str]],
    workspace_id: Optional[str] = None,
    form_ids: Optional[Sequence[str]] = None,
) -> Optional[Set[str]]:
    """The forms a run is limited to, or None for all. ``workspace_id`` keeps the
    forms linked to that workspace; ``form_ids`` the listed ones; both, the
    forms satisfying both."""
    # an empty filter never means "everything": it is refused
    if (workspace_id is not None and not str(workspace_id).strip()) or (
        form_ids is not None and len(form_ids) == 0
    ):
        raise ValueError("an empty workspace or form filter")
    allowed: Optional[Set[str]] = None
    if workspace_id is not None:
        allowed = {f for f, workspaces in links.items() if workspace_id in workspaces}
    if form_ids is not None:
        listed = {str(f) for f in form_ids}
        allowed = listed if allowed is None else allowed & listed
    return allowed


# --------------------------------------------------------------------- stores
class PostgresStore(PostgresBase):
    @staticmethod
    def _row(collection: str):
        from backend.db.models import FormResponseRow, ResponseDeletionRequestRow

        return {
            "form_responses": FormResponseRow,
            "responses_deletion_requests": ResponseDeletionRequestRow,
        }[collection]

    async def unstamped(self, collection: str, after, limit: int) -> List[dict]:
        from sqlalchemy import select

        from common.db.canonical import from_canonical_document

        row = self._row(collection)
        columns = [row.id, row.form_id, row.response_id]
        if collection == "form_responses":
            columns += [row.doc[field] for field in ENCRYPTED_FIELDS]
        stmt = select(*columns).where(row.workspace_id.is_(None))
        if after is not None:
            stmt = stmt.where(row.id > after)
        stmt = stmt.order_by(row.id).limit(limit)
        records = []
        async with self.engine.connect() as conn:
            for values in await conn.execute(stmt):
                record = {
                    "key": values[0],
                    "form_id": values[1],
                    "response_id": values[2],
                }
                if collection == "form_responses":
                    encrypted = {
                        field: value
                        for field, value in zip(ENCRYPTED_FIELDS, values[3:])
                        if value is not None
                    }
                    record.update(from_canonical_document(encrypted))
                records.append(record)
        return records

    async def response_workspaces(self, response_ids: Iterable[str]) -> Dict[str, str]:
        from sqlalchemy import select

        from backend.db.models import FormResponseRow as r

        ids = list(set(response_ids))
        if not ids:
            return {}
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                select(r.response_id, r.workspace_id).where(
                    r.response_id.in_(ids), r.workspace_id.is_not(None)
                )
            )
            return {response_id: workspace for response_id, workspace in rows}

    async def stamp(self, collection: str, key, workspace_id: str) -> int:
        from sqlalchemy.exc import IntegrityError

        try:
            return await self._stamp(collection, key, workspace_id)
        except IntegrityError as e:
            orig = e.orig
            code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
            if code == "23505":  # unique violation
                raise StampConflict() from None
            raise

    async def _stamp(self, collection: str, key, workspace_id: str) -> int:
        from sqlalchemy import select, update

        from common.db.canonical import checksum

        table = self._row(collection).__table__
        async with self.engine.begin() as conn:
            doc = (
                await conn.execute(
                    select(table.c.doc)
                    .where(table.c.id == key, table.c.workspace_id.is_(None))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return 0
            # the document as the application would store it, and its checksum
            doc = {**doc, "workspace_id": {"$oid": workspace_id}}
            await conn.execute(
                update(table)
                .where(table.c.id == key)
                .values({"doc": doc, "_bc_checksum": checksum(doc)})
            )
        return 1


STORE_CLASSES = {"postgres": PostgresStore}


# ------------------------------------------------------------------------ run
async def _stamp(store, counts: Counter, collection: str, key, workspace: str) -> None:
    try:
        counts["stamped"] += await store.stamp(collection, key, workspace)
    except StampConflict:
        counts["conflict"] += 1


async def backfill_store(
    store,
    apply: bool,
    opens: Optional[Opener],
    batch_size: int = 500,
    *,
    workspace_id: Optional[str] = None,
    form_ids: Optional[Sequence[str]] = None,
    resume: Optional[Dict[str, Any]] = None,
    on_batch: Optional[OnBatch] = None,
) -> Dict[str, Any]:
    """Backfill one store. ``resume`` is ``{"phase": ..., "after": <key>}`` (the
    key already decoded): the phase to continue and the last key handled in it.
    ``on_batch`` is called after each batch is handled (and stamped)."""
    links = await store.links()
    attributor = Attributor(links, opens)
    allowed = allowed_forms(links, workspace_id, form_ids)
    report: Dict[str, Any] = {
        "forms_linked_to_several_workspaces": sum(
            1 for workspaces in links.values() if len(workspaces) > 1
        )
    }
    planned: Dict[str, str] = {}  # response_id -> workspace, this run
    seen = 0
    stopped = False

    def selected(record: Dict[str, Any]) -> bool:
        return allowed is None or str(record.get("form_id")) in allowed

    resume_phase = resume["phase"] if resume else PHASES[0]

    counts: Counter = Counter()
    if resume_phase == PHASES[0]:
        after = resume["after"] if resume else None
        while True:
            batch = await store.unstamped("form_responses", after, batch_size)
            if not batch:
                break
            after = batch[-1]["key"]
            for record in batch:
                if not selected(record):
                    continue
                seen += 1
                counts["unstamped"] += 1
                bucket, workspace = attributor.response(record)
                counts[bucket] += 1
                if workspace is None:
                    continue
                if record.get("response_id"):
                    planned[str(record["response_id"])] = workspace
                if apply:
                    await _stamp(
                        store, counts, "form_responses", record["key"], workspace
                    )
            if on_batch is not None and await on_batch(PHASES[0], after, seen):
                stopped = True
                break
        report["responses"] = dict(counts)

    counts = Counter()
    if not stopped:
        after = resume["after"] if resume and resume_phase == PHASES[1] else None
        while True:
            batch = await store.unstamped("responses_deletion_requests", after, batch_size)
            if not batch:
                break
            after = batch[-1]["key"]
            batch_records = [r for r in batch if selected(r)]
            stored = await store.response_workspaces(
                str(r["response_id"]) for r in batch_records if r.get("response_id")
            )
            for record in batch_records:
                seen += 1
                counts["unstamped"] += 1
                response_id = str(record.get("response_id"))
                workspace = planned.get(response_id) or stored.get(response_id)
                if workspace is not None:
                    bucket = "from_response"
                else:
                    bucket, workspace = attributor.by_form(record.get("form_id"))
                counts[bucket] += 1
                if workspace is not None and apply:
                    await _stamp(
                        store,
                        counts,
                        "responses_deletion_requests",
                        record["key"],
                        workspace,
                    )
            if on_batch is not None and await on_batch(PHASES[1], after, seen):
                stopped = True
                break
        report["deletion_requests"] = dict(counts)
    if stopped:
        report["complete"] = False
    return report


async def run(
    stores,
    apply: bool,
    opens=None,
    batch_size: int = 500,
    **options: Any,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "encryption_key": opens is not None,
        "stores": {},
    }
    for store in stores:
        report["stores"][store.name] = await backfill_store(
            store, apply, opens, batch_size, **options
        )
    return report
