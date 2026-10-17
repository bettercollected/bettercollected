"""The form editor's operations (ops.py "Editor ops"): refused on every
surface that is not the editor, absent from what the AI and MCP clients are
told, exported in the committed ops schema. What they do is pinned by the
shared corpus (test_form_ops_corpus.py)."""

import json
import re

import pytest
from common.models.standard_form import StandardForm
from pydantic import ValidationError

from backend.app.services.ai import ops_schema
from backend.app.services.ai.chat import _ChatTurnReply
from backend.app.services.ai.ops import (
    EDITOR_ONLY_OPS,
    OP_NAMES,
    apply_form_ops,
    parse_ops,
)
from backend.app.services.ai.prompt_builder import OPS_GUIDE
from backend.app.services.ai.review import _coerce_finding
from backend.app.services.form_spec.service import ops_errors
from tests.app.services.test_form_ops_corpus import _corpus, from_document

MINIMAL = {
    "insert_field": {
        "pageId": "p1",
        "index": 0,
        "field": {"id": "n", "type": "short_text"},
    },
    "replace_field": {"field": {"id": "a", "type": "long_text"}},
    "insert_page": {"index": 0, "page": {"id": "p9", "type": "slide"}},
    "update_page": {"pageId": "p1", "patch": {"layout": None}},
    "update_welcome_page": {"patch": {"title": "Hi"}},
    "set_hidden_fields": {"names": ["utm_source"]},
    "update_logo": {"alt": "Logo"},
    "set_choice": {"fieldId": "a", "choiceId": "c", "value": "x"},
    "add_choice": {"fieldId": "a", "choice": {"id": "c"}},
    "remove_choice": {"fieldId": "a", "choiceId": "c"},
    "move_choice": {"fieldId": "a", "choiceId": "c", "index": 0},
}
EDITOR_ONLY_MESSAGE = "only available in the form editor"


def _payload(name):
    return {"op": name, **MINIMAL[name]}


def test_every_editor_op_has_a_minimal_payload():
    assert set(MINIMAL) == EDITOR_ONLY_OPS
    assert EDITOR_ONLY_OPS <= OP_NAMES


@pytest.mark.parametrize("name", sorted(EDITOR_ONLY_OPS))
def test_parse_ops_refuses_each_editor_op_at_its_index(name):
    payload = [{"op": "update_form_info", "title": "x"}, _payload(name)]
    with pytest.raises(ValidationError) as raised:
        parse_ops(payload)
    [error] = raised.value.errors()
    assert error["loc"][:2] == ("ops", 1)
    assert EDITOR_ONLY_MESSAGE in error["msg"] and name in error["msg"]
    # the public API and dry runs report it at the op's path
    assert ops_errors(raised.value) == [{"path": "/ops/1", "message": error["msg"]}]
    # the editor may send it
    [_, op] = parse_ops(payload, allow_editor_ops=True)
    assert op.op == name


def test_each_refused_op_gets_its_own_error():
    payload = [
        _payload("insert_field"),
        {"op": "remove_field", "fieldId": "x"},
        _payload("update_logo"),
    ]
    with pytest.raises(ValidationError) as raised:
        parse_ops(payload)
    assert [e["loc"][:2] for e in raised.value.errors()] == [("ops", 0), ("ops", 2)]


def test_the_ai_chat_reply_refuses_editor_ops():
    with pytest.raises(ValidationError) as raised:
        _ChatTurnReply.model_validate(
            {"reply": "Done", "ops": [_payload("insert_page")]}
        )
    assert "invalid operations" in str(raised.value)
    assert EDITOR_ONLY_MESSAGE in str(raised.value)


def test_a_review_fix_with_an_editor_op_is_dropped():
    finding = _coerce_finding(
        {
            "severity": "high",
            "message": "Ask less",
            "fix": {"description": "Remove", "ops": [_payload("set_hidden_fields")]},
        }
    )
    assert finding is not None and finding.fix is None
    kept = _coerce_finding(
        {
            "severity": "high",
            "message": "Ask less",
            "fix": {"ops": [{"op": "remove_field", "fieldId": "a"}]},
        }
    )
    assert kept.fix is not None


def _mentions(text: str, name: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", text) is not None


def test_the_ops_guide_never_mentions_editor_ops():
    for name in EDITOR_ONLY_OPS:
        assert not _mentions(OPS_GUIDE, name), name


async def test_the_mcp_tools_never_mention_editor_ops():
    from backend.app.mcp.server import mcp

    tools = await mcp.list_tools()
    assert tools
    for tool in tools:
        text = (tool.description or "") + json.dumps(tool.inputSchema)
        for name in EDITOR_ONLY_OPS:
            assert not _mentions(text, name), (tool.name, name)


def test_refs_reach_an_editor_op():
    form = from_document("small", _corpus()["forms"])
    ops = parse_ops(
        [
            {"op": "add_page", "ref": "new"},
            {
                "op": "insert_field",
                "pageId": "$ref:new",
                "index": 0,
                "field": {"id": "x", "type": "short_text"},
            },
        ],
        allow_editor_ops=True,
    )
    after, results = apply_form_ops(form, ops, atomic=True)
    assert all(r.ok for r in results), [r.message for r in results]
    assert after.fields[1].properties.fields[0].id == "x"


def test_an_image_already_on_the_form_is_kept():
    """As on a whole-form save: an address the form already holds may stay
    (forms saved before the image checks), a new foreign one may not."""
    old = "https://images.example.org/legacy.png"
    form = StandardForm(
        builder_version="v2",
        fields=[
            {
                "id": "p1",
                "type": "slide",
                "image_url": old,
                "properties": {
                    "fields": [{"id": "a", "type": "short_text", "title": "A"}]
                },
            }
        ],
    )
    keep = parse_ops(
        [
            {
                "op": "replace_field",
                "field": {"id": "a", "type": "short_text", "imageUrl": old},
            }
        ],
        allow_editor_ops=True,
    )
    _, results = apply_form_ops(form, keep)
    assert results[0].ok, results[0].message
    refuse = parse_ops(
        [
            {
                "op": "replace_field",
                "field": {"id": "a", "type": "short_text", "imageUrl": old + "?x"},
            }
        ],
        allow_editor_ops=True,
    )
    _, results = apply_form_ops(form, refuse)
    assert not results[0].ok


def test_the_committed_ops_schema_is_current():
    assert ops_schema.main(["--check"]) == 0, (
        "docs/spec/form-ops-v1.schema.json is stale: "
        "run python -m backend.app.services.ai.ops_schema"
    )


def test_the_schema_check_notices_a_stale_file(tmp_path, monkeypatch):
    stale = tmp_path / "schema.json"
    stale.write_text("{}\n")
    monkeypatch.setattr(ops_schema, "SCHEMA_PATH", stale)
    assert ops_schema.main(["--check"]) == 1


def test_the_schema_marks_editor_ops():
    schema = ops_schema.build_schema()
    assert schema["x-editorOnlyOps"] == sorted(EDITOR_ONLY_OPS)
    marked = {
        d["properties"]["op"]["const"]
        for d in schema["$defs"].values()
        if d.get("x-editorOnly")
    }
    assert marked == EDITOR_ONLY_OPS
    ops = schema["properties"]["ops"]["items"]["oneOf"]
    assert len(ops) == len(OP_NAMES)


def test_every_corpus_op_matches_the_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(ops_schema.SCHEMA_PATH.read_text())
    item = schema["properties"]["ops"]["items"]
    validator = jsonschema.Draft202012Validator({"$defs": schema["$defs"], **item})
    for case in _corpus()["cases"]:
        refused = case["expect"].get("error", {}).get("index")
        for index, op in enumerate(case["ops"]):
            if index == refused:
                continue  # may be refused for its shape, when it is applied
            errors = list(validator.iter_errors(op))
            assert not errors, (case["name"], op["op"], errors[0].message)


RICH_TITLE = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hi"}]}],
}


def test_a_rich_text_title_comes_only_from_the_editor():
    payload = [{"op": "update_field", "fieldId": "a", "patch": {"title": RICH_TITLE}}]
    with pytest.raises(ValidationError) as raised:
        parse_ops(payload)
    assert "rich-text titles come only from the form editor" in str(raised.value)
    with pytest.raises(ValidationError):
        _ChatTurnReply.model_validate({"reply": "x", "ops": payload})
    [op] = parse_ops(payload, allow_editor_ops=True)
    assert op.patch.title == RICH_TITLE
    # plain titles are as before everywhere
    [op] = parse_ops([{"op": "update_field", "fieldId": "a", "patch": {"title": "Hi"}}])
    assert op.patch.title == "Hi"


def test_a_title_with_an_unknown_node_type_is_refused():
    form = from_document("small", _corpus()["forms"])
    title = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "mention", "attrs": {"id": "x"}}],
            }
        ],
    }
    for op in (
        {"op": "update_field", "fieldId": "a", "patch": {"title": title}},
        {
            "op": "insert_field",
            "pageId": "p1",
            "index": 0,
            "field": {"id": "n", "type": "short_text", "title": title},
        },
    ):
        after, results = apply_form_ops(form, parse_ops([op], allow_editor_ops=True))
        assert not results[0].ok
        assert "cannot hold a 'mention' node" in results[0].message
        assert after.model_dump() == form.model_dump()


def test_pruning_counts_only_what_the_op_removed():
    form = from_document("small", _corpus()["forms"])
    document = form.model_dump()
    # an older orphan: logic on a question that is long gone
    document["fields"][0]["properties"]["fields"][1]["properties"] = {
        "logic": {
            "action": "SHOW",
            "conditions": [
                {"fieldId": "gone-long-ago", "comparison": "IS_NOT_EMPTY"},
                {"fieldId": "a", "comparison": "IS_NOT_EMPTY"},
            ],
        }
    }
    form = StandardForm.model_validate(document)
    after, results = apply_form_ops(
        form, parse_ops([{"op": "remove_field", "fieldId": "a"}])
    )
    assert results[0].ok
    assert "(and 1 logic or piping reference(s) to it)" in results[0].message
    # both are gone, as in the editor
    assert after.fields[0].properties.fields[0].properties.logic is None


def test_a_jump_to_a_removed_page_stays():
    form = from_document("base", _corpus()["forms"])
    after, results = apply_form_ops(
        form, parse_ops([{"op": "remove_page", "pageId": "p3"}])
    )
    assert results[0].ok
    targets = [j.target for j in after.fields[1].properties.jumps]
    assert "p3" in targets


def test_image_checks_never_copy_the_form(monkeypatch):
    """A batch of editor ops on a large form copies it a fixed number of
    times (the working copy and the final check), never once per op."""
    form = from_document(
        {"$generated": {"pages": 20, "fieldsPerPage": 90}}, _corpus()["forms"]
    )
    copies = {"deep": 0}
    original = StandardForm.model_copy

    def counting(self, *args, **kwargs):
        if kwargs.get("deep"):
            copies["deep"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(StandardForm, "model_copy", counting)
    unsplash = "https://images.unsplash.com/photo-1500000000000-abcdef"
    ops = []
    for i in range(50):
        ops += [
            {
                "op": "insert_field",
                "pageId": "p0",
                "index": 0,
                "field": {"id": f"n{i}", "type": "short_text", "imageUrl": unsplash},
            },
            {"op": "replace_field", "field": {"id": f"p1f{i}", "type": "long_text"}},
            {"op": "update_page", "pageId": "p2", "patch": {"imageUrl": unsplash}},
            {"op": "update_welcome_page", "patch": {"title": f"T{i}"}},
        ]
    _, results = apply_form_ops(
        form, parse_ops(ops, allow_editor_ops=True), atomic=True
    )
    assert all(r.ok for r in results), [r.message for r in results if not r.ok][:3]
    assert copies["deep"] <= 3
