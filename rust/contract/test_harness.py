"""Self-tests of the harness: the comparison rules, the corpus expansion and the
row diff. Pure Python, no servers, no database.

    uv run --project backend pytest rust/contract -q
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import corpus  # noqa: E402
import dbdiff  # noqa: E402
from compare import IGNORED_HEADERS, Answer, compare  # noqa: E402


def answer(status=200, headers=None, body=b"{}", ct="application/json"):
    heads = {"content-type": [ct]} if ct else {}
    heads.update({k.lower(): v if isinstance(v, list) else [v] for k, v in (headers or {}).items()})
    return Answer(status, heads, body)


# ------------------------------------------------------------------ compare

def test_json_is_compared_after_parse_not_as_text():
    a = answer(body=b'{"a": 1, "b": [1, 2]}')
    b = answer(body=b'{"b":[1,2],"a":1}')
    assert compare(a, b).equal


def test_a_changed_value_a_status_or_a_security_header_is_a_difference():
    base = answer(body=b'{"a":1}', headers={"cache-control": "no-store"})
    assert not compare(base, answer(body=b'{"a":2}', headers={"cache-control": "no-store"})).equal
    assert not compare(base, answer(status=201, body=b'{"a":1}', headers={"cache-control": "no-store"})).equal
    missing = compare(base, answer(body=b'{"a":1}'))
    assert not missing.equal and "cache-control" in missing.differences[0]
    cookies = compare(
        answer(headers={"set-cookie": ["a=1", "b=2"]}), answer(headers={"set-cookie": ["a=1"]})
    )
    assert not cookies.equal


def test_only_the_listed_transport_headers_are_ignored():
    a = answer(headers={"date": "x", "server": "uvicorn", "content-length": "2", "x-bc-served-by": "rust"})
    b = answer(headers={"date": "y", "server": "axum", "content-length": "3"})
    assert compare(a, b).equal
    # CORS, caching, cookies, vary and allow are never on the list
    for name in ("access-control-allow-origin", "cache-control", "set-cookie", "vary", "allow", "location"):
        assert name not in IGNORED_HEADERS


def test_a_non_json_body_must_be_byte_equal():
    a = answer(body=b"Internal server error", ct="text/plain; charset=utf-8")
    assert compare(a, answer(body=b"Internal server error", ct="text/plain; charset=utf-8")).equal
    assert not compare(a, answer(body=b"Internal Server Error", ct="text/plain; charset=utf-8")).equal


def test_a_failed_request_is_a_difference_not_a_pass():
    ok = answer()
    broken = Answer(0, {}, b"", error="ConnectionRefusedError")
    assert not compare(ok, broken).equal
    assert not compare(broken, broken).equal


# ------------------------------------------------------------------- corpus

FIXTURE = {
    "workspaces": {"main": "6a0000000000000000000001", "other": "6a0000000000000000000002"},
    "people": {"owner": {"id": "6a00000000000000000000aa", "email": "o@example.test"}},
    "tokens": {"owner": "T-owner", "viewer": "T-viewer", "old": None},
}


def test_placeholders_and_matrices_expand_in_order():
    cases = corpus.expand(
        {
            "name": "p:{who}@{w}",
            "method": "GET",
            "path": "/ws/{ws.{w}}/x",
            "headers": {"Cookie": "A={token.{who}}"},
            "matrix": {"who": ["owner", "viewer"], "w": "@workspaces"},
        },
        {"served_by": "rust"},
        FIXTURE,
        "g",
        "f.json",
    )
    assert [c.name for c in cases] == [
        "p:owner@main", "p:owner@other", "p:viewer@main", "p:viewer@other",
    ]
    assert cases[1].path == "/ws/6a0000000000000000000002/x"
    assert cases[2].headers == {"Cookie": "A=T-viewer"}
    assert all(c.served_by == "rust" for c in cases)


def test_a_null_token_skips_the_case_and_an_unknown_placeholder_is_an_error():
    skipped = corpus.expand(
        {"name": "n", "method": "GET", "path": "/", "headers": {"Cookie": "{token.old}"}}, {}, FIXTURE, "g", "f"
    )
    assert skipped == []
    with pytest.raises(corpus.CorpusError):
        corpus.expand({"name": "n", "method": "GET", "path": "/{ws.nope}"}, {}, FIXTURE, "g", "f")
    with pytest.raises(corpus.CorpusError):
        corpus.expand({"name": "n", "method": "GET", "path": "/", "served_by": "elsewhere"}, {}, FIXTURE, "g", "f")


def test_a_json_body_is_filled_and_typed():
    (case,) = corpus.expand(
        {"name": "w", "method": "post", "path": "/x", "json": {"owner": "{person.owner.id}"}}, {}, FIXTURE, "g", "f"
    )
    assert case.method == "POST"
    assert json.loads(case.body) == {"owner": "6a00000000000000000000aa"}
    assert case.headers["Content-Type"] == "application/json"


def test_a_body_can_be_built_from_repeated_pieces():
    (case,) = corpus.expand(
        {
            "name": "deep",
            "method": "POST",
            "path": "/x",
            "body_parts": ["[", ["[", 2], " ", ["x", 3], "]"],
            "content_type": "application/json",
        },
        {},
        FIXTURE,
        "g",
        "f",
    )
    assert case.body == b"[[[ xxx]"
    assert case.headers["Content-Type"] == "application/json"


def test_the_shipped_corpus_is_well_formed():
    """Every file names its group and env, every case has a name, a method and a
    path, and every placeholder is a fixture reference or a matrix variable."""
    import re

    files = sorted((Path(__file__).parent / "cases").glob("*.json"))
    assert files
    total = 0
    for path in files:
        raw = json.loads(path.read_text())
        assert re.fullmatch(r"[a-z][a-z0-9_-]*", raw["group"]), path.name
        assert isinstance(raw.get("env", {}), dict)
        for case in raw["cases"]:
            total += 1
            assert {"name", "method", "path"} <= set(case), (path.name, case)
            assert case.get("served_by", raw.get("defaults", {}).get("served_by")) in (None, "rust", "python")
            variables = set((case.get("matrix") or {}))
            text = json.dumps(case)
            for ref in re.findall(r"\{([a-z_]+)[.}]", text):
                assert ref in variables | {"ws", "token", "person"}, (path.name, case["name"], ref)
    assert total > 50


# ------------------------------------------------------------------- dbdiff

def row(row_id, doc, **extra):
    return {"id": row_id, "doc": doc, "created_at": "t0", "updated_at": "t0",
            "_bc_checksum": dbdiff.checksum_of(doc), **extra}


def test_the_checksum_is_sha256_of_the_canonical_json():
    # sorted keys, no whitespace, not ASCII-only
    assert dbdiff.canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'
    assert dbdiff.checksum_of({"a": 1}).startswith("sha256:")
    snap = {"t": {"1": row("1", {"a": 1}), "2": {**row("2", {"a": 1}), "_bc_checksum": "sha256:bad"}}}
    assert dbdiff.bad_checksums(snap) == ["t/2"]


def test_diff_names_added_removed_and_changed_rows():
    before = {"t": {"1": row("1", {"a": 1}), "2": row("2", {"a": 2})}}
    after = {"t": {"1": row("1", {"a": 9}), "3": row("3", {"a": 3})}}
    delta = dbdiff.diff(before, after)
    assert set(delta["t"]["added"]) == {"3"} and set(delta["t"]["removed"]) == {"2"}
    assert delta["t"]["changed"]["1"]["doc"] == [{"a": 1}, {"a": 9}]
    assert dbdiff.diff(before, before) == {}


def test_two_runs_that_made_the_same_change_with_other_ids_and_times_are_equal():
    def new_row(row_id, when):
        doc = {"_id": {"$oid": row_id}, "title": "T", "ref": row_id, "created": {"$date": when}}
        return {**row(row_id, doc), "created_at": when, "updated_at": when, "title": "T"}

    py = dbdiff.diff({"t": {}}, {"t": {"aaaaaaaaaaaaaaaaaaaaaaaa": new_row("aaaaaaaaaaaaaaaaaaaaaaaa", "2026-01-01")}})
    rs = dbdiff.diff({"t": {}}, {"t": {"bbbbbbbbbbbbbbbbbbbbbbbb": new_row("bbbbbbbbbbbbbbbbbbbbbbbb", "2026-02-02")}})
    assert dbdiff.compare_deltas(py, rs) == []


def test_a_different_doc_or_spine_column_or_row_count_is_a_difference():
    def made(doc, spine="x"):
        return dbdiff.diff({"t": {}}, {"t": {"i": {**row("i", doc), "workspace_id": spine}}})

    assert dbdiff.compare_deltas(made({"a": 1}), made({"a": 1})) == []
    assert dbdiff.compare_deltas(made({"a": 1}), made({"a": 2}))
    assert dbdiff.compare_deltas(made({"a": 1}, "w1"), made({"a": 1}, "w2"))
    assert dbdiff.compare_deltas(made({"a": 1}), {})


def test_a_table_name_cannot_carry_sql():
    with pytest.raises(ValueError):
        dbdiff._table('workspaces"; DROP TABLE x; --')


def test_python_only_environment_is_read_from_the_corpus_file(tmp_path):
    path = tmp_path / "f.json"
    path.write_text(json.dumps({
        "group": "g", "env": {"A": "1"}, "python_env": {"B": 2},
        "cases": [{"name": "c", "method": "GET", "path": "/"}],
    }))
    loaded = corpus.load_file(path, FIXTURE)
    assert loaded.env == {"A": "1"} and loaded.python_env == {"B": "2"}
    path.write_text(json.dumps({"group": "g", "cases": []}))
    assert corpus.load_file(path, FIXTURE).python_env == {}


def test_store_rows_tampering_and_refused_starts_are_read_from_the_corpus_file(tmp_path):
    base = {"group": "g", "cases": []}

    def load(extra):
        path = tmp_path / "f.json"
        path.write_text(json.dumps({**base, **extra}))
        return corpus.load_file(path, FIXTURE)

    loaded = load({"env": {"A": None, "B": 1}, "store": {"SSO_ENABLED": True}, "tamper": [{"op": "manifest_sig"}, {"op": "value", "key": "K", "value": 1}]})
    assert loaded.env == {"A": None, "B": "1"} and loaded.store == {"SSO_ENABLED": True} and len(loaded.tamper) == 2
    assert load({}).store is None and load({}).expect_start is None and load({}).rust_env == {}
    edge = load({"rust_env": {"SETTINGS_MASTER_KEY": None, "DATABASE_URL": "@EDGE_ROLE_URL", "N": 3}})
    assert edge.rust_env == {"SETTINGS_MASTER_KEY": None, "DATABASE_URL": "@EDGE_ROLE_URL", "N": "3"}
    assert load({"store": {}, "expect_start": "refused"}).expect_start == "refused"
    for bad in (
        {"store": ["x"]},
        {"tamper": [{"op": "value"}]},
        {"store": {}, "tamper": [{"op": "drop"}]},
        {"tamper": [{"op": "manifest_sig"}]},  # nothing to tamper with
        {"store": {}, "expect_start": "served"},
        {"store": {}, "expect_start": "refused", "cases": [{"name": "x", "method": "GET", "path": "/"}]},
    ):
        with pytest.raises(corpus.CorpusError):
            load(bad)


def test_the_settings_registry_file_of_the_rust_reader_is_current():
    """rust/bc-config/data/settings-registry.json is written from the Python registry; it must not drift."""
    import settings_registry

    try:
        built = settings_registry.render(settings_registry.build())
    except ImportError as error:  # a plain environment without the backend's dependencies
        pytest.skip(f"the backend is not importable here: {error.name}")
    assert settings_registry.OUT.read_text() == built, (
        "run `uv run --project backend python rust/contract/settings_registry.py`"
    )


def test_the_placeholders_of_the_edge_environment_are_resolved():
    import run

    out = run.resolve_rust_env(
        {"A": None, "B": "plain", "C": "@RANDOM_KEY", "D": "@EDGE_ROLE_URL"}, {"edge_role_url": "postgresql://r:p@h/d"}
    )
    assert out["A"] is None and out["B"] == "plain" and out["D"] == "postgresql://r:p@h/d"
    assert len(out["C"]) >= 64 and out["C"] != run.resolve_rust_env({"C": "@RANDOM_KEY"}, {})["C"]
