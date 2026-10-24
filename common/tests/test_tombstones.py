"""Deletion tombstones: the victim rule, merging two stores' tombstones, and
the Mongo collection wrapper that records a tombstone before each delete."""

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo.errors import BulkWriteError

from common.clock import write_clock
from common.db import tombstones
from common.db.tombstones import TombstoningCollection, is_victim, merge

T = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def test_a_copy_written_before_the_delete_is_a_victim():
    assert is_victim(T, T - timedelta(seconds=1))
    assert is_victim(T, (T - timedelta(seconds=1)).isoformat())  # Mongo stores ISO text
    assert is_victim(T, None)  # no usable timestamp: older than any delete


def test_times_compare_at_millisecond_precision():
    """Postgres keeps microseconds, Mongo milliseconds: a copy written by the
    deleting write itself is not a victim in either store."""
    at = T.replace(microsecond=123456)
    assert not is_victim(at, at.replace(microsecond=123000))
    assert not is_victim(at.replace(microsecond=123000), at)
    assert is_victim(at, at.replace(microsecond=122999))


def test_a_copy_written_at_or_after_the_delete_is_not():
    assert not is_victim(T, T)  # the same routed write deleted and wrote it again
    assert not is_victim(T, T + timedelta(seconds=1))
    assert not is_victim(None, T - timedelta(days=1))


def test_merge_keeps_the_latest_delete_per_id():
    naive = (T + timedelta(hours=1)).replace(tzinfo=None)  # pymongo hands out naive UTC
    merged = merge({"a": T, "b": T}, {"a": naive})
    assert merged == {"a": T + timedelta(hours=1), "b": T}


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self):
        return self._docs


class FakeCollection:
    """Just enough of a pymongo collection: documents are dicts with an _id
    and a ``k``; filters are ``{}``, ``{"k": v}`` or ``$and`` of those and
    ``{"_id": x}`` / ``{"_id": {"$in": [...]}}``."""

    def __init__(self, name, database, docs=()):
        self.name, self.database, self.docs = name, database, list(docs)
        self.log = []

    def _match(self, doc, flt):
        if "$and" in flt:
            return all(self._match(doc, f) for f in flt["$and"])
        for key, want in flt.items():
            if isinstance(want, dict) and "$in" in want:
                if doc.get(key) not in want["$in"]:
                    return False
            elif doc.get(key) != want:
                return False
        return True

    def find(self, flt, projection=None, session=None):
        return FakeCursor([d for d in self.docs if self._match(d, flt)])

    async def find_one(self, flt, projection=None, session=None, sort=None):
        found = [d for d in self.docs if self._match(d, flt)]
        return found[0] if found else None

    async def delete_one(self, flt, session=None):
        self.log.append(("delete_one", flt))
        for d in self.docs:
            if self._match(d, flt):
                self.docs.remove(d)
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()

    async def delete_many(self, flt, session=None):
        self.log.append(("delete_many", flt))
        gone = [d for d in self.docs if self._match(d, flt)]
        self.docs = [d for d in self.docs if d not in gone]
        return type("R", (), {"deleted_count": len(gone)})()

    async def insert_many(self, docs, ordered=True, session=None):
        self.log.append(("tombstones", [d["row_id"] for d in docs]))
        errors = []
        for index, doc in enumerate(docs):
            if any(d["_id"] == doc["_id"] for d in self.docs):
                errors.append({"index": index, "code": 11000})
            else:
                self.docs.append(dict(doc))
        if errors:
            raise BulkWriteError({"writeErrors": errors})

    async def update_many(self, flt, update, session=None):
        for d in self.docs:
            if self._match(d, flt):
                d.update(update["$set"])


class FakeDatabase(dict):
    def __getitem__(self, name):
        if name not in self:
            self[name] = FakeCollection(name, self)
        return dict.__getitem__(self, name)


async def test_delete_many_records_each_id_before_deleting_exactly_those():
    db = FakeDatabase()
    a, b, c = ObjectId(), ObjectId(), ObjectId()
    db["forms"] = FakeCollection(
        "forms", db, [{"_id": a, "k": 1}, {"_id": b, "k": 1}, {"_id": c, "k": 2}]
    )
    wrapped = TombstoningCollection(db["forms"])
    with write_clock() as now:
        result = await wrapped.delete_many({"k": 1})

    assert result.deleted_count == 2
    assert [d["_id"] for d in db["forms"].docs] == [c]
    stones = db[tombstones.COLLECTION].docs
    assert {s["row_id"] for s in stones} == {str(a), str(b)}
    assert all(set(s) == {"_id", "collection", "row_id", "deleted_at"} for s in stones)
    assert all(
        s["collection"] == "forms" and s["deleted_at"] == tombstones.to_ms(now)
        for s in stones
    )
    # the tombstones were written before the delete, which names the ids
    tombstoned_at = db[tombstones.COLLECTION].log
    assert tombstoned_at and db["forms"].log[0][1]["$and"][1] == {
        "_id": {"$in": [a, b]}
    }


async def test_delete_one_records_the_matched_id_and_nothing_when_none_matches():
    db = FakeDatabase()
    a = ObjectId()
    db["forms"] = FakeCollection("forms", db, [{"_id": a, "k": 1}])
    wrapped = TombstoningCollection(db["forms"])

    assert (await wrapped.delete_one({"k": 2})).deleted_count == 0
    assert db[tombstones.COLLECTION].docs == []
    assert (await wrapped.delete_one({"k": 1})).deleted_count == 1
    assert [s["row_id"] for s in db[tombstones.COLLECTION].docs] == [str(a)]


def test_only_initialised_document_classes_get_the_wrapper_once():
    class Settings:
        def __init__(self, name):
            self.name = name
            self.pymongo_collection = FakeCollection(name, FakeDatabase())

    def model(name):
        settings = Settings(name)
        return type(name, (), {"get_settings": staticmethod(lambda: settings)})

    forms, outbox = model("forms"), model("mirror_write_failures")
    tombstones.tombstone_deletes([forms, outbox, object])
    tombstones.tombstone_deletes([forms])
    wrapped = forms.get_settings().pymongo_collection
    assert isinstance(wrapped, TombstoningCollection)
    assert not isinstance(wrapped.wrapped, TombstoningCollection)
    assert not isinstance(
        outbox.get_settings().pymongo_collection, TombstoningCollection
    )


async def test_deleting_an_id_again_moves_its_tombstone_forward():
    db = FakeDatabase()
    with write_clock():
        await tombstones.record_mongo(db, "forms", ["a"])
    db[tombstones.COLLECTION].docs[0]["deleted_at"] = T
    await tombstones.record_mongo(db, "forms", ["a", "b"])
    stones = {s["row_id"]: s["deleted_at"] for s in db[tombstones.COLLECTION].docs}
    assert set(stones) == {"a", "b"} and stones["a"] > T
