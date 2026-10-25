"""Whether the 4.0 forms import is complete, as far as the forms' workspace
links go.

The forms group is served from Postgres only since 4.1; a 4.0 database's
``workspace_forms`` stay in Mongo until ``python -m backend.migrate --group
forms backfill`` copies them. Until that copy is complete, the links in
Postgres are a subset of the real ones: a form linked to two workspaces may
show only one. Anything that decides which workspace a response belongs to,
or whether an account has forms, from the Postgres links must not act on
such a subset. Its tools refuse with :data:`CODE` (writes) or warn (reads)
until every link Mongo holds is in Postgres too.

The import counts as complete when EITHER

- a finished backfill of ``workspace_forms`` is recorded in
  ``migration_progress`` (``done``, nothing skipped: the signal the startup
  guard trusts too, ``backend.db.mongo_import_guard``) AND Mongo holds no
  ``workspace_forms`` document past its last copied ``_id`` (one 4.0 wrote
  after the import: a rollback, a rehearsal on the same database). This
  covers links deleted after the import: since 4.1 they are deleted in
  Postgres only, so they stay in Mongo's frozen copy for good; or
- every ``(form_id, workspace_id)`` link in Mongo's ``workspace_forms`` is in
  Postgres (a link only Postgres has, made after the import, is fine). A
  backfill that is not finished, or skipped documents, falls back to this.

Every role that runs the check may read ``migration_progress``'s
``collection``, ``state``, ``last_id`` and ``skipped`` (the task runner's
data role by ``postgres/ensure-admin-roles.sh``); one that may not falls back
to the second check, with a warning. Counts only are reported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Set, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

#: the refusal code (admin tasks, the case-duplicate accounts routes)
CODE = "forms_import_incomplete"

#: the message the tools print or log with it (no ids, counts only)
MESSAGE = (
    "the forms import is incomplete: {missing} workspace link(s) of forms in "
    "Mongo are not in Postgres. Run `python -m backend.migrate --group forms "
    "backfill` (and verify the counts) first."
)

Pair = Tuple[str, str]


class FormsImportIncomplete(RuntimeError):
    """Mongo holds workspace links of forms that Postgres does not."""

    code = CODE

    def __init__(self, missing: int):
        super().__init__(MESSAGE.format(missing=missing))
        self.missing = missing


def pairs(links: Mapping[str, Iterable[str]]) -> Set[Pair]:
    """``{form_id: [workspace ids]}`` -> its ``(form_id, workspace_id)`` pairs."""
    return {
        (str(form_id), str(workspace))
        for form_id, workspaces in links.items()
        for workspace in workspaces
    }


async def mongo_links(database) -> Dict[str, List[str]]:
    """``{form_id: [workspace ids]}`` of the 4.0 ``workspace_forms`` in Mongo
    (``database``: a pymongo AsyncDatabase, read only), in insertion order;
    links without a workspace are left out."""
    links: Dict[str, List[str]] = {}
    cursor = (
        database["workspace_forms"]
        .find({}, {"form_id": 1, "workspace_id": 1})
        .sort("_id", 1)
    )
    async for row in cursor:
        if not row.get("workspace_id"):
            continue
        workspaces = links.setdefault(str(row.get("form_id")), [])
        if str(row["workspace_id"]) not in workspaces:
            workspaces.append(str(row["workspace_id"]))
    return links


async def missing_links(database, postgres_links: Mapping[str, Iterable[str]]) -> int:
    """How many of Mongo's workspace links of forms Postgres lacks (0: the
    import of the links is complete)."""
    return len(pairs(await mongo_links(database)) - pairs(postgres_links))




@dataclass(frozen=True)
class Backfill:
    """What ``migration_progress`` records of the ``workspace_forms`` backfill."""

    #: finished (``done``) without skipping a document
    complete: bool
    #: the highest Mongo ``_id`` it copied (None: none)
    last_id: Optional[str] = None


async def workspace_forms_backfill(engine) -> Optional[Backfill]:
    """The ``workspace_forms`` backfill as recorded (``engine``: a SQLAlchemy
    AsyncEngine); None when this role may not read ``migration_progress``."""
    from backend.db.models import MigrationProgress
    from common.db.migrate.progress import STATE_DONE

    progress = MigrationProgress.__table__
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    select(progress.c.state, progress.c.last_id, progress.c.skipped).where(
                        progress.c.collection == "workspace_forms"
                    )
                )
            ).first()
    except DBAPIError as error:
        # a fail-safe: every role that runs this check is granted these
        # columns (postgres/ensure-admin-roles.sh for the task runner)
        logger.warning(
            "The forms import check cannot read migration_progress ({}): it "
            "compares the links only. Grant SELECT (collection, state, last_id, "
            "skipped) on it.",
            type(error).__name__,
        )
        return None
    if row is None:
        return Backfill(complete=False)
    return Backfill(
        complete=row.state == STATE_DONE and not row.skipped, last_id=row.last_id
    )


async def written_after(database, last_id: Optional[str]) -> int:
    """How many ``workspace_forms`` documents Mongo holds past the backfill's
    last copied ``_id`` (all of them when it copied none): links 4.0 wrote
    after the import (a rollback, a rehearsal on the same database). Counts
    an indexed ``_id`` range only."""
    from bson import ObjectId

    query = {"_id": {"$gt": ObjectId(last_id)}} if last_id else {}
    return await database["workspace_forms"].count_documents(query)


async def unimported_links(
    database, postgres_links: Mapping[str, Iterable[str]], engine=None
) -> int:
    """0 when the forms import is complete (see the module docstring), else
    how many of Mongo's links it lacks. Raises PyMongoError when Mongo cannot
    be read (the callers refuse then)."""
    backfill = None if engine is None else await workspace_forms_backfill(engine)
    if backfill is not None and backfill.complete:
        return await written_after(database, backfill.last_id)
    return await missing_links(database, postgres_links)


async def import_problem(
    database, postgres_links: Mapping[str, Iterable[str]], engine=None
) -> Optional[Tuple[str, str]]:
    """None when the forms import is complete, else ``(code, message)``:
    :data:`CODE` with the count of missing links, or ``store_unreachable``
    when Mongo cannot be read (it is then unknown, so callers that write
    refuse)."""
    from pymongo.errors import PyMongoError

    try:
        missing = await unimported_links(database, postgres_links, engine)
    except PyMongoError as error:
        return (
            "store_unreachable",
            f"Mongo could not be read ({type(error).__name__}): whether the forms "
            "import is complete is unknown.",
        )
    if missing:
        return CODE, MESSAGE.format(missing=missing)
    return None
