"""Scenario-style parity: run the same scenario against each store, compare the records.

For repositories whose writes mint ids: each store mints its own, so results are
compared with those ids replaced by stable labels (``ids.label``), and with the
fields that legitimately differ (timestamps) stripped. Optionally the documents
each store ended up holding are compared too, as stored (the bytes ``verify``
checksums), not as the repository hands them back.
"""

from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from bson import ObjectId
from sqlalchemy import select

from common.db import canonical_document, canonical_json
from common.db.routing import normalise_result

VOLATILE = {"created_at", "updated_at", "revision_id"}


class Ids:
    """Labels for the ids a scenario mints, so two stores' results compare."""

    def __init__(self) -> None:
        self._labels: Dict[str, str] = {}

    def label(self, value: Any, name: str) -> Any:
        self._labels[str(value)] = f"<{name}>"
        return value

    def normalise(self, value: Any) -> Any:
        value = normalise_result(value)
        if isinstance(value, ObjectId):
            value = str(value)
        if isinstance(value, dict):
            if set(value) == {"$oid"}:  # a stored ObjectId
                return self.normalise(value["$oid"])
            return {k: self.normalise(v) for k, v in value.items() if k not in VOLATILE}
        if isinstance(value, list):
            return [self.normalise(v) for v in value]
        if isinstance(value, str):
            return self._labels.get(value, value)
        return value


class Record(list):
    """The steps' results, snapshotted when recorded (documents are mutable)."""

    def append(self, value: Any) -> None:
        super().append(normalise_result(value))


async def _stored(
    tables: Iterable[Tuple[type, type]], sessions, ids_by_store: List[Ids]
) -> List[Dict[str, List[str]]]:
    """Each store's documents per collection, normalised and in a stable order."""
    mongo_ids, postgres_ids = ids_by_store
    mongo, postgres = {}, {}
    for document_cls, row in tables:
        name = document_cls.get_settings().name
        raw = await document_cls.get_pymongo_collection().find({}).to_list()
        mongo[name] = sorted(
            canonical_json(mongo_ids.normalise(canonical_document(d))) for d in raw
        )
        async with sessions() as session:
            docs = (await session.execute(select(row.doc))).scalars().all()
        postgres[name] = sorted(canonical_json(postgres_ids.normalise(d)) for d in docs)
    return [mongo, postgres]


async def run_on_both(
    scenario: Callable[[Any, "Ids", List[Any]], Any],
    mongo: Any,
    postgres: Any,
    *,
    stored: Optional[Iterable[Tuple[type, type]]] = None,
    sessions=None,
) -> None:
    """``scenario(repo, ids, record)`` appends what each step returned to ``record``.

    With ``stored=[(DocumentClass, Row), ...]`` the documents left in each
    store afterwards must be identical too (ids as labels, timestamps aside).
    """
    results, all_ids = [], []
    for repo in (mongo, postgres):
        ids, record = Ids(), Record()
        await scenario(repo, ids, record)
        results.append([ids.normalise(step) for step in record])
        all_ids.append(ids)
    mongo_steps, postgres_steps = results
    assert len(mongo_steps) == len(postgres_steps)
    for index, (m, p) in enumerate(zip(mongo_steps, postgres_steps)):
        assert m == p, f"step {index} differs: mongo={m!r} postgres={p!r}"
    if stored:
        in_mongo, in_postgres = await _stored(stored, sessions, all_ids)
        assert in_mongo == in_postgres
