"""``python -m auth.migrate``: one repository group and the marker table.
(The engine itself runs against real stores in the backend and google suites;
this suite has no real Mongo.)"""

import pytest

from auth.migrate.__main__ import _tables, build_target
from common.db.migrate.cli import build_parser, main, select_collections


def _target():
    return build_target("postgresql+asyncpg://unused/unused_test")


def test_every_collection_is_in_the_auth_group():
    target = _target()
    assert target.service == "auth" and target.group_names() == ["auth"]
    assert set(target.groups) == set(_tables())
    assert target.marker is not None and target.marker.name == "store_migration"
    assert "+schema.0004" in target.code_version


def test_group_auth_selects_everything_and_others_are_refused(capsys):
    target = _target()
    args = build_parser("python -m auth.migrate").parse_args(
        ["--group", "auth", "verify"]
    )
    assert select_collections(args, target) == list(target.tables)
    with pytest.raises(SystemExit) as exit_:
        main(["--group", "identity", "backfill"], target, prog="python -m auth.migrate")
    assert exit_.value.code == 2
    assert "valid groups: auth" in capsys.readouterr().err
