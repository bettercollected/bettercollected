"""The shared conformance corpus of the edit operations
(docs/spec/form-ops-v1.cases.json, format in docs/spec/README.md): each case
applies its operations to its form with the backend's engine (ops.py) and
must give the expected form or error."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
from common.models.standard_form import StandardForm

from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.services.ai.ops import EDITOR_ONLY_OPS, apply_form_ops, parse_ops

CASES_PATH = (
    Path(__file__).resolve().parents[4] / "docs" / "spec" / "form-ops-v1.cases.json"
)
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def generated_form(spec: Dict[str, int]) -> Dict[str, Any]:
    """A ``{"$generated": {"pages": n, "fieldsPerPage": m}}`` form: pages
    ``p<i>``, each with short text questions ``p<i>f<j>`` titled "Q"."""
    return {
        "title": "Generated",
        "builderVersion": "v2",
        "fields": [
            {
                "id": f"p{p}",
                "index": p,
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": f"p{p}f{f}",
                            "index": f,
                            "type": "short_text",
                            "title": "Q",
                        }
                        for f in range(spec["fieldsPerPage"])
                    ]
                },
            }
            for p in range(spec["pages"])
        ],
    }


def from_document(document: Any, forms: Dict[str, Any]) -> StandardForm:
    """A case's form (the editor's camelCase document, the name of one of
    the corpus's ``forms``, or a generated one) read as a whole-form save
    reads it."""
    if isinstance(document, str):
        document = forms[document]
    if "$generated" in document:
        document = generated_form(document["$generated"])
    return StandardForm(**FormDtoCamelModel(**document).model_dump(mode="json"))


def to_document(form: StandardForm) -> Dict[str, Any]:
    return FormDtoCamelModel(**form.model_dump(mode="json")).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def normalise_ids(document: Any) -> Any:
    """Generated uuids replaced by ``$uuid:<n>``, numbered by order of
    appearance: depth first, object keys in sorted order."""
    names: Dict[str, str] = {}

    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: walk(value[key]) for key in sorted(value)}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str) and UUID.match(value):
            names.setdefault(value, f"$uuid:{len(names) + 1}")
            return names[value]
        return value

    return walk(document)


def run_case(
    case: Dict[str, Any], forms: Dict[str, Any], compute: bool = False
) -> Dict[str, Any]:
    before = from_document(case["before"], forms)
    ops = parse_ops(case["ops"], allow_editor_ops=True)
    after, results = apply_form_ops(before, ops, atomic=case["atomic"])
    document = normalise_ids(to_document(after))
    unchanged = document == normalise_ids(to_document(before))
    if compute:
        return {"results": results, "form": document, "changed": not unchanged}
    expect = case["expect"]
    error = expect.get("error")
    if error is None:
        assert all(r.ok for r in results), [r.message for r in results if not r.ok]
    else:
        index = error["index"]
        assert all(r.ok for r in results[:index]), [r.message for r in results]
        assert not results[index].ok, results[index].message
        assert error["messageContains"] in results[index].message
        if case["atomic"]:
            assert unchanged
    if "form" in expect:
        assert document == expect["form"]
    return {"results": results, "form": document, "changed": not unchanged}


def _corpus() -> Dict[str, Any]:
    return json.loads(CASES_PATH.read_text())


def _cases() -> List[Dict[str, Any]]:
    return _corpus()["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_case(case):
    run_case(case, _corpus()["forms"])


def test_the_corpus_is_large_and_covers_every_editor_op():
    cases = _cases()
    assert len(cases) >= 80
    assert len({case["name"] for case in cases}) == len(cases)
    used = {op["op"] for case in cases for op in case["ops"]}
    assert EDITOR_ONLY_OPS <= used
    for name in EDITOR_ONLY_OPS:
        refused = [
            case
            for case in cases
            if "error" in case["expect"]
            and case["ops"][case["expect"]["error"]["index"]]["op"] == name
        ]
        if name not in ("move_choice", "update_welcome_page", "remove_choice"):
            assert refused, f"no refusal case for {name}"
    assert any(case["atomic"] for case in cases)
    assert any("error" in c["expect"] and not c["atomic"] for c in cases)


def test_ids_are_numbered_by_order_of_appearance():
    a = "0b1c6a8e-1111-4c4c-9d9d-000000000001"
    b = "0b1c6a8e-1111-4c4c-9d9d-000000000002"
    assert normalise_ids({"z": a, "a": [b, a], "keep": "p1"}) == {
        "a": ["$uuid:1", "$uuid:2"],
        "keep": "p1",
        "z": "$uuid:2",
    }
