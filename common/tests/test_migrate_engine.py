"""Pure pieces of the migration engine (the database-driven parts are exercised
by the backend suite against both stores)."""

from datetime import datetime, timezone

from bson import ObjectId
from sqlalchemy import Column, MetaData, Table, Text, UniqueConstraint, Computed

from common.db.base import SOURCE_BACKFILL
from common.db.canonical import checksum, canonical_document
from common.db.migrate.engine import (
    MAX_BATCH,
    MIN_BATCH,
    adapt_batch,
    is_object_id,
    row_from_document,
    spine_paths,
    timestamp_of,
    unique_key_paths,
)


def test_object_ids_are_recognised_in_both_shapes():
    oid = ObjectId()
    assert is_object_id(oid) and is_object_id(str(oid))
    assert not is_object_id("not-an-id") and not is_object_id(42)


def test_timestamps_are_read_as_beanie_stores_them():
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert timestamp_of(aware) == aware
    assert timestamp_of(datetime(2026, 1, 2, 3, 4, 5)) == aware  # naive → UTC
    assert timestamp_of("2026-01-02T03:04:05Z") == aware
    assert timestamp_of("2026-01-02T03:04:05") == aware
    assert timestamp_of("garbage") is None and timestamp_of(None) is None


def test_backfilled_row_carries_the_document_checksum_and_source():
    document = {
        "_id": ObjectId(),
        "title": "t",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    row = row_from_document(document)
    assert row["id"] == str(document["_id"]) and row["_bc_source"] == SOURCE_BACKFILL
    assert row["_bc_checksum"] == checksum(canonical_document(document))
    assert row["created_at"] == document["created_at"] and row["updated_at"] is not None


def test_unique_keys_are_read_off_the_spine_columns():
    metadata = MetaData(schema="app")
    table = Table(
        "workspace_forms",
        metadata,
        Column("id", Text, primary_key=True),
        Column(
            "workspace_id",
            Text,
            Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
        ),
        Column(
            "form_id", Text, Computed("app.bc_text(doc -> 'form_id')", persisted=True)
        ),
        Column(
            "custom_url",
            Text,
            Computed("app.bc_text(doc -> 'settings' -> 'custom_url')", persisted=True),
        ),
        UniqueConstraint("workspace_id", "form_id"),
    )
    assert spine_paths(table) == {
        "workspace_id": ["workspace_id"],
        "form_id": ["form_id"],
        "custom_url": ["settings", "custom_url"],
    }
    assert unique_key_paths(table) == [[["workspace_id"], ["form_id"]]]


def test_batch_size_adapts_within_bounds():
    assert (
        adapt_batch(200, seconds=25) == 100 and adapt_batch(30, seconds=25) == MIN_BATCH
    )
    assert (
        adapt_batch(200, seconds=1) == 400
        and adapt_batch(MAX_BATCH, seconds=1) == MAX_BATCH
    )
    assert adapt_batch(200, seconds=10) == 200
