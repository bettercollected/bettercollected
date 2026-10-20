"""Golden fixtures of the ``doc`` codec for every backend document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``.
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from backend.app.container import container
from backend.app.handlers.database import document_models
from backend.db.base import Base
from common.db import BaseRow, PostgresRepositoryBase, canonical_json, checksum
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    load,
    mirrored_documents,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "codec_golden" / "backend.json"

# Tables written only by the migration (raw documents, no Beanie class); their
# codec path is covered by common/tests/test_codec_golden.py.
NO_DOCUMENT_CLASS = {"scheduler_form_configs"}

# Values the synthesizer cannot guess (a field validator with a checksum).
OVERRIDES = {"coupon_codes": {"code": "A" * 24 + "0"}}


def _rows():
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]


def _documents():
    return mirrored_documents(_rows(), document_models)


def test_every_mirrored_table_has_a_document_class_or_is_listed(_initialized_app):
    missing = sorted(c for c, cls in _documents().items() if cls is None)
    assert missing == sorted(NO_DOCUMENT_CLASS)


def test_encoding_matches_the_pinned_bytes(_initialized_app):
    documents = {c: cls for c, cls in _documents().items() if cls is not None}
    assert check(FIXTURE, build_cases(documents, OVERRIDES)) == []


def test_decode_then_encode_gives_the_pinned_bytes(_initialized_app):
    classes = {cls.__name__: cls for cls in document_models}
    assert check_round_trip(FIXTURE, classes) == []


async def test_postgres_stores_and_returns_the_pinned_bytes(clean_postgres):
    """JSONB keeps every pinned value (large integers, floats, Extended JSON tags)."""
    tables = {row.mongo_collection(): row for row in _rows()}
    store = PostgresRepositoryBase(container.pg_sessionmaker())
    now = datetime.now(timezone.utc)
    problems = []
    for name, case in sorted(load(FIXTURE).items()):
        row = tables[name.split("/")[0]]
        row_id = case["doc"]["_id"]["$oid"]
        values = {
            "id": row_id,
            "doc": case["doc"],
            "created_at": now,
            "updated_at": now,
            "bc_source": "app",
            "bc_checksum": case["checksum"],
        }
        async with store._session() as session, session.begin():
            await session.execute(store._upsert_statement(values, row))
        async with store._session() as session:
            stored = (
                await session.execute(
                    select(row.doc, row.bc_checksum).where(row.id == row_id)
                )
            ).one()
        async with store._session() as session, session.begin():
            await session.execute(delete(row).where(row.id == row_id))
        if canonical_json(stored.doc) != canonical_json(case["doc"]):
            problems.append(f"{name}: doc changed in Postgres")
        if case["checksum"] != checksum(stored.doc) or (
            case["checksum"] != stored.bc_checksum
        ):
            problems.append(f"{name}: checksum changed in Postgres")
    assert problems == []
