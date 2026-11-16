"""How deeply a JSON body may nest: the scan that runs before anything parses
it (utils/json_depth.py), the limit against what clients legitimately send,
and the parse helper the places that read a body with ``json.loads`` use."""

import json
import time
from pathlib import Path

import pytest

from backend.app.exceptions import HTTPException
from backend.app.utils.json_depth import MAX_JSON_DEPTH, loads, too_deep
from backend.app.services.ai.ops import TITLE_JSON_MAX_DEPTH
from backend.app.services.form_spec.service import parse_json_document
from backend.app.services.idempotency import request_hash

LIMIT = MAX_JSON_DEPTH


def arrays(n: int) -> str:
    return "[" * n + "]" * n


def objects(n: int) -> str:
    return '{"a":' * n + "1" + "}" * n


def mixed(n: int) -> str:
    """Arrays and objects alternating, n levels."""
    opening = ['{"a":' if i % 2 else "[" for i in range(n)]
    closing = ["}" if i % 2 else "]" for i in reversed(range(n))]
    return "".join(opening) + "1" + "".join(closing)


def depth_of(value) -> int:
    deepest, pending = 0, [(value, 1)]
    while pending:
        item, level = pending.pop()
        if isinstance(item, dict):
            deepest = max(deepest, level)
            pending.extend((v, level + 1) for v in item.values())
        elif isinstance(item, list):
            deepest = max(deepest, level)
            pending.extend((v, level + 1) for v in item)
    return deepest


def both(text: str):
    """The scan of the text and of its bytes agree."""
    verdict = too_deep(text)
    assert too_deep(text.encode()) is verdict
    assert too_deep(bytearray(text.encode())) is verdict
    return verdict


# -- the limit ------------------------------------------------------------------


def test_the_limit_is_well_below_where_the_parser_fails_and_above_what_clients_send():
    # json.loads of Python 3.11 reads about 990 levels with nothing else on the stack
    assert LIMIT * 4 < 983


@pytest.mark.parametrize("shape", [arrays, objects, mixed])
def test_exactly_at_the_limit_is_accepted_and_one_more_is_refused(shape):
    assert both(shape(LIMIT)) is False
    assert both(shape(LIMIT + 1)) is True
    assert both(shape(LIMIT - 1)) is False


@pytest.mark.parametrize("shape", [arrays, objects, mixed])
@pytest.mark.parametrize("levels", [983, 984, 5000, 200_000])
def test_a_body_beyond_what_the_parser_reads_is_refused_not_parsed(shape, levels):
    assert both(shape(levels)) is True


def test_the_depth_counts_levels_not_brackets():
    # wide, not deep
    assert both("[" + ",".join(["[]"] * 10_000) + "]") is False
    assert both(json.dumps([{"a": [1, 2, {"b": [3]}]}] * 5_000)) is False
    # siblings never add up
    assert both(("[" * 100 + "]" * 100) * 50) is False


def test_the_scan_agrees_with_the_real_depth_of_valid_documents():
    for n in (1, 2, 10, LIMIT - 1, LIMIT, LIMIT + 1):
        assert depth_of(json.loads(objects(n))) == n
        assert depth_of(json.loads(mixed(n))) == n
        assert both(objects(n)) is (n > LIMIT)


# -- strings and escapes ----------------------------------------------------------


def test_brackets_inside_strings_are_not_counted():
    assert both(json.dumps(["[" * 500, "{" * 500, "]" * 500])) is False
    assert both(json.dumps({"[" * 300: "{" * 300})) is False
    assert both('"' + "[" * 500 + '"') is False
    # the string closes and the brackets after it count again
    assert both('"[[["' + "[" * LIMIT) is False
    assert both('"[[["' + "[" * (LIMIT + 1)) is True


def test_an_escaped_quote_does_not_end_a_string():
    # ["\"[[[[...": the quote is escaped, the string stays open
    assert both('["\\"' + "[" * 500 + '"]') is False
    # the same text with the quote not escaped: the string ends at it
    assert both('["x"' + "[" * 500 + '"]') is True
    # an escaped backslash does not escape the quote after it
    assert both('["\\\\"' + "[" * 500 + "]") is True
    assert both('["\\\\\\"' + "[" * 500 + '"]') is False
    # escapes of other kinds
    assert both(json.dumps(['a\nb\t"c" \\   [[[[', "x" * 10])) is False


def test_a_string_that_never_ends_swallows_the_rest():
    assert both('["' + "[" * 500) is False
    assert both('["abc\\') is False
    assert both('"' + "[" * 500 + "\\") is False


def test_stray_closers_buy_no_extra_levels():
    assert both("]" * 500 + "[" * (LIMIT + 1)) is True
    assert both("}" * 500 + "[" * LIMIT) is False


def test_text_that_is_not_json_is_left_to_the_parser():
    for junk in ("", "[", "]", "{not json", "\x00" * 100, "[" * 50 + "garbage", "é" * 100):
        assert both(junk) is False


def test_non_ascii_text_does_not_confuse_the_scan():
    text = json.dumps({"title": "Voornaam éè \U0001f600" * 50, "x": [["[", "]"]]})
    assert both(text) is False
    assert too_deep(text.encode("utf-8")) is False
    assert both(json.dumps("é" * 100, ensure_ascii=False) + "[" * (LIMIT + 1)) is True


# -- cost -------------------------------------------------------------------------


def test_the_scan_is_linear_not_a_recursion_and_does_not_choke_on_hostile_strings():
    big = json.dumps([{"a": "x" * 5, "b": [1, 2, {"c": "[[["}]} for _ in range(30_000)]).encode()
    assert len(big) > 1_000_000
    started = time.monotonic()
    assert too_deep(big) is False
    # a quote escaped over and over, then a quote that never closes: no retrying at every quote
    assert too_deep(b'"' + b'\\"' * 500_000 + b"[[" * 500) is False
    assert too_deep(b'"\\"' * 300_000) is False
    assert too_deep(b"[" * 5_000_000) is True
    assert time.monotonic() - started < 5


def test_a_body_with_fewer_openers_than_the_limit_is_not_scanned_at_all():
    # (the count is a shortcut: the answer is the same as the full scan's)
    assert both(json.dumps({"a": [1, 2, 3]})) is False
    assert both("[" * LIMIT) is False


# -- the limit against what clients really send -------------------------------------


def nest_title(depth: int) -> dict:
    """A rich-text title as deep as ``depth`` (nodes are objects holding a
    ``content`` array: two levels each)."""
    node = {"type": "text", "text": "x"}
    while depth_of(node) + 2 <= depth:
        node = {"type": "paragraph", "content": [node]}
    return node


def expression_at_the_limit() -> dict:
    """An expression nested as deeply as a form accepts (31 operators, each a
    list inside an object: a form refuses 32)."""
    node = 1
    for _ in range(31):
        node = {"+": [node, 1]}
    return node


def test_the_deepest_legitimate_documents_fit_with_room_to_spare():
    # a form as the builder saves it: form > fields > page > fields > question >
    # a rich-text title at the deepest it may nest (TITLE_JSON_MAX_DEPTH)
    title = nest_title(TITLE_JSON_MAX_DEPTH)
    assert depth_of(title) >= TITLE_JSON_MAX_DEPTH - 1
    form = {
        "title": "x",
        "fields": [
            {
                "id": "p",
                "type": "slide",
                "properties": {"fields": [{"id": "a", "type": "short_text", "title": title}]},
            }
        ],
    }
    ops = {"ops": [{"op": "update_field", "field": "a", "title": title}]}
    # an expression at the deepest a form accepts, in a rule of a question on a page
    rule = {"id": "r1", "when": {"expression": expression_at_the_limit()}, "then": {"required": True}}
    ruled = {
        "title": "x",
        "fields": [
            {
                "id": "p",
                "type": "slide",
                "properties": {
                    "fields": [{"id": "a", "type": "number", "properties": {"rules": [rule]}}]
                },
            }
        ],
    }
    deepest = max(depth_of(document) for document in (form, ops, ruled))
    # about 70 levels at worst: more than 40 levels of room under the limit
    assert deepest < LIMIT - 40, deepest
    for document in (form, ops, ruled):
        assert both(json.dumps(document)) is False


def test_the_form_builder_payload_at_the_expression_limit_still_parses():
    from backend.app.controllers.workspace_forms import _parse_form_body

    node = expression_at_the_limit()
    body = json.dumps(
        {
            "title": "x",
            "builderVersion": "v2",
            "fields": [
                {
                    "id": "p",
                    "type": "slide",
                    "properties": {
                        "fields": [
                            {
                                "id": "a",
                                "type": "short_text",
                                "properties": {
                                    "rules": [
                                        {"id": "r1", "when": {"expression": node}, "then": {"required": True}}
                                    ]
                                },
                            }
                        ]
                    },
                }
            ],
        }
    )
    assert too_deep(body) is False
    assert _parse_form_body(body).fields[0].properties.fields[0].properties.rules


FIXTURE_DIRS = ("docs/spec", "docs/api", "backend/tests/fixtures", "rust/contract")


def test_every_json_fixture_and_spec_example_in_the_repository_fits():
    root = Path(__file__).resolve().parents[4]
    files = [p for d in FIXTURE_DIRS for p in (root / d).rglob("*.json")] if (root / "docs").is_dir() else []
    if not files:
        pytest.skip("the repository's documents are not here")
    deepest = 0
    for path in files:
        raw = path.read_bytes()
        try:
            deepest = max(deepest, depth_of(json.loads(raw)))
        except ValueError:
            continue  # (not a JSON document)
        assert too_deep(raw) is False, path.name
    assert deepest < LIMIT, deepest


# -- the parse helper ---------------------------------------------------------------


def test_loads_parses_what_json_parses():
    assert loads('{"a": [1, 2, {"b": null}]}') == {"a": [1, 2, {"b": None}]}
    assert loads(b'["x"]') == ["x"]
    assert loads(bytearray(b"[1]")) == [1]
    assert loads(arrays(LIMIT)) == json.loads(arrays(LIMIT))


@pytest.mark.parametrize("body", ["", "{not json", "[1,", "nope"])
def test_loads_leaves_other_problems_to_json(body):
    with pytest.raises(ValueError):
        loads(body)


def test_loads_leaves_a_missing_value_to_json_too():
    with pytest.raises(TypeError):
        loads(None)


@pytest.mark.parametrize("body", [arrays(LIMIT + 1), objects(5000), mixed(100_000)])
@pytest.mark.parametrize("kind", [str, bytes])
def test_loads_refuses_a_body_that_is_too_deep_with_422_body_too_deep(body, kind):
    with pytest.raises(HTTPException) as error:
        loads(kind(body, "utf-8") if kind is bytes else body)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "body_too_deep"
    assert "nested too deeply" in error.value.content["message"]


def test_loads_also_turns_a_recursion_error_into_the_refusal(monkeypatch):
    """The scan is the first defence; if the parser still runs out of stack
    (a stack that is already deep), the answer is the same."""
    import backend.app.utils.json_depth as module

    def exhausted(raw):
        raise RecursionError

    monkeypatch.setattr(module.json, "loads", exhausted)
    with pytest.raises(HTTPException) as error:
        module.loads("[1]")
    assert error.value.content["code"] == "body_too_deep"


# -- the places that parse a body themselves -----------------------------------------


def test_the_public_api_reader_refuses_a_deep_body_with_the_same_answer():
    with pytest.raises(HTTPException) as error:
        parse_json_document(objects(5000).encode())
    assert error.value.status_code == 422
    assert error.value.content["code"] == "body_too_deep"
    # not JSON at all keeps its own answer
    with pytest.raises(HTTPException) as error:
        parse_json_document(b"{nope")
    assert error.value.content == {"message": "The body is not valid JSON."}
    assert parse_json_document(arrays(LIMIT).encode()) == json.loads(arrays(LIMIT))


@pytest.mark.parametrize("levels", [LIMIT + 1, 983, 984, 5000, 100_000])
def test_the_idempotency_fingerprint_survives_a_deep_body(levels):
    """It read the body with json.loads and only expected a ValueError: a body
    nested past the parser's stack raised a RecursionError (a 500)."""
    body = arrays(levels).encode()
    first = request_hash("POST", "/forms", body)
    assert first == request_hash("POST", "/forms", body)
    assert first != request_hash("POST", "/forms", arrays(levels + 1).encode())
    # a document is still compared by value
    assert request_hash("POST", "/x", b'{"a": 1, "b": 2}') == request_hash(
        "POST", "/x", b'{"b":2,"a":1}'
    )
