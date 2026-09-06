import pytest
from sqlalchemy import Computed

from common.db import SpineColumns, drop_helper_function_ddl, helper_function_ddl
from common.db.base import BaseRow, make_base


def test_spine_columns_render_schema_qualified_generated_expressions():
    S = SpineColumns("app")
    Base = make_base("app")

    class Row(Base, BaseRow):
        __tablename__ = "spine_probe"
        form_id = S.text("form_id")
        custom_url = S.text("settings", "custom_url")
        published_at = S.ts("published_at")
        is_default = S.bool("default", name="is_default")
        version = S.int("version")

    cols = {c.name: c for c in Row.__table__.columns}
    assert isinstance(cols["form_id"].computed, Computed)
    assert cols["form_id"].computed.sqltext.text == "app.bc_text(doc -> 'form_id')"
    assert (
        cols["custom_url"].computed.sqltext.text
        == "app.bc_text(doc #> '{settings,custom_url}')"
    )
    assert (
        cols["published_at"].computed.sqltext.text == "app.bc_ts(doc -> 'published_at')"
    )
    assert cols["is_default"].computed.sqltext.text == "app.bc_bool(doc -> 'default')"
    assert cols["version"].computed.sqltext.text == "app.bc_int(doc -> 'version')"
    assert all(
        cols[n].computed.persisted for n in ("form_id", "custom_url", "published_at")
    )


@pytest.mark.parametrize("bad", ["", "settings.custom_url", "x y", "a;drop"])
def test_unsafe_keys_are_rejected_at_definition_time(bad):
    with pytest.raises(ValueError):
        SpineColumns("app").text(bad)


def test_mongo_collection_defaults_to_table_name():
    Base = make_base("google")

    class A(Base, BaseRow):
        __tablename__ = "google_forms"
        __mongo_collection__ = "GoogleFormDocument"

    class B(Base, BaseRow):
        __tablename__ = "plain"

    assert A.mongo_collection() == "GoogleFormDocument"
    assert B.mongo_collection() == "plain"


def test_helper_ddl_is_per_schema_and_immutable():
    ddl = helper_function_ddl("auth")
    assert len(ddl) == 4
    assert all("auth.bc_" in s and "IMMUTABLE" in s for s in ddl)
    assert (
        drop_helper_function_ddl("auth")[0]
        == "DROP FUNCTION IF EXISTS auth.bc_text(jsonb)"
    )
    with pytest.raises(ValueError):
        helper_function_ddl("Bad-Schema")
