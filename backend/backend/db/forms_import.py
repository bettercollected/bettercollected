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
  ``migration_progress``: the signal the startup guard trusts too
  (``backend.db.mongo_import_guard``: an empty table with a finished backfill
  is the application's doing, not a missing import). It also covers links
  deleted after the import: since 4.1 they are deleted in Postgres only, so
  they stay in Mongo's frozen copy for good; or
- every ``(form_id, workspace_id)`` link in Mongo's ``workspace_forms`` is in
  Postgres (a link only Postgres has, made after the import, is fine).

A role that may not read ``migration_progress`` (the task runner's data role)
gets the second check only. Counts only are reported.
"""

from __future__ import annotations

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




async def backfill_finished(engine) -> Optional[bool]:
    """Whether ``migration_progress`` records a finished backfill of
    ``workspace_forms`` (``engine``: a SQLAlchemy AsyncEngine); None when
    this role may not read it."""
    from backend.db.models import MigrationProgress
    from common.db.migrate.progress import STATE_DONE

    progress = MigrationProgress.__table__
    try:
        async with engine.connect() as conn:
            found = (
                await conn.execute(
                    select(progress.c.collection).where(
                        progress.c.collection == "workspace_forms",
                        progress.c.state == STATE_DONE,
                    )
                )
            ).first()
    except DBAPIError as error:
        logger.info(
            "The forms import check cannot read migration_progress ({}): it "
            "compares the links only.",
            type(error).__name__,
        )
        return None
    return found is not None


async def unimported_links(
    database, postgres_links: Mapping[str, Iterable[str]], engine=None
) -> int:
    """0 when the forms import is complete (see the module docstring), else
    how many of Mongo's links Postgres lacks. Raises PyMongoError when Mongo
    cannot be read (the callers refuse then)."""
    if engine is not None and await backfill_finished(engine):
        return 0
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
