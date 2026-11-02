"""The tables of form-level access exist only in Postgres: 4.0 never had them in
Mongo, so the import guard must not probe, import or verify them (the
Mongo-driven marker test checks the same in CI; this one needs no Mongo)."""

import backend.db.models  # noqa: F401  registers every table
from backend.db.base import Base
from common.db.migrate.import_guard import NOT_IMPORTED_TABLES, collection_tables

NEW = {"member_groups", "member_group_members", "form_access_grants"}


def test_the_new_tables_are_not_imported_tables():
    assert NEW <= set(NOT_IMPORTED_TABLES)
    assert len(set(NOT_IMPORTED_TABLES)) == len(NOT_IMPORTED_TABLES)


def test_the_guard_does_not_see_them_as_collections():
    probed = {table.name for table in collection_tables(Base).values()}
    assert not NEW & probed


def test_the_tables_are_declared_on_the_app_schema():
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    for name in NEW:
        assert tables[name].schema == "app"
