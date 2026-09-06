from sqlalchemy import UniqueConstraint

from common.db import BaseRow, make_base
from common.db.base import ID_CHECK_NAME


def test_models_with_their_own_table_args_keep_the_id_check():
    Base = make_base("meta_test")

    class WithArgs(Base, BaseRow):
        __tablename__ = "with_args"
        __table_args__ = (UniqueConstraint("_bc_checksum", name="just_for_the_test"),)

    names = {str(c.name) for c in WithArgs.__table__.constraints}
    # the naming convention prefixes check constraints with ck_<table>_
    assert any(n.endswith(ID_CHECK_NAME) for n in names), names
    assert "just_for_the_test" in names


def test_each_base_has_its_own_schema_and_naming_convention():
    app, auth = make_base("app"), make_base("auth")
    assert app.metadata.schema == "app" and auth.metadata.schema == "auth"
    assert app.metadata is not auth.metadata
    assert "ck" in app.metadata.naming_convention
