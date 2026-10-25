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

The comparison is of ``(form_id, workspace_id)`` pairs only: a link Postgres
has and Mongo does not (made after the import) is fine; a link Mongo has and
Postgres does not is a missing import. Counts only are reported.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Set, Tuple

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


async def ensure_imported(database, postgres_links: Mapping[str, Iterable[str]]) -> None:
    """Raise :class:`FormsImportIncomplete` unless Postgres holds every
    workspace link of forms that Mongo holds."""
    missing = await missing_links(database, postgres_links)
    if missing:
        raise FormsImportIncomplete(missing)
