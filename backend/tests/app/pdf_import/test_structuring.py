"""Structuring: model answers are grounded on word and layout ids, validated,
retried once, and replaced by deterministic structuring when unusable."""

import io

import pdfplumber
import pytest

from backend.app.services.pdf_import.layout import page_layout
from backend.app.services.pdf_import.structuring import (
    describe,
    expand_refs,
    heuristic,
    merge,
    page_context,
    schema,
    structure_page,
    validate,
)
from backend.app.services.pdf_import.text_layer import page_words
from tests.app.pdf_import import documents

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def ctx():
    with pdfplumber.open(io.BytesIO(documents.form_pdf())) as pdf:
        page = pdf.pages[0]
        words = page_words(page)
        layout = page_layout(page, words["words"])
    return page_context(words, layout, 1, "text")


def ids_of(ctx, *texts):
    out = []
    for t in texts:
        out.append(next(f"w{i}" for i, w in enumerate(ctx.words) if w["text"] == t))
    return out


def prim(ctx, kind, n=0):
    return [p["id"] for p in ctx.primitives if p["kind"] == kind][n]


class FakeProvider:
    supports_vision = True

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    async def analyze_page(self, system, prompt, image, schema):
        self.calls.append({"prompt": prompt, "image": image})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def good_answer(ctx):
    return {
        "sections": [{"id": "s1", "title_refs": ids_of(ctx, "Personal", "details")}],
        "questions": [
            {
                "id": "q1",
                "kind": "short_text",
                "label_refs": ids_of(ctx, "Full", "name"),
                "slot_refs": [prim(ctx, "answer_slot")],
                "section": "s1",
                "required": True,
            },
            {
                "id": "q2",
                "kind": "single_choice",
                "label_refs": ids_of(ctx, "Gender"),
                "slot_refs": [prim(ctx, "checkbox", 0), prim(ctx, "checkbox", 1)],
                "options": [
                    {"refs": ids_of(ctx, "Male")},
                    {"refs": ids_of(ctx, "Female")},
                ],
            },
        ],
        "statements": [],
        "staff_only": [{"refs": [prim(ctx, "staff_region")]}],
        "ignore": [],
    }


def test_schema_and_description(ctx):
    s = schema()
    assert (
        "questions" in s["properties"]
        and "short_text"
        in s["properties"]["questions"]["items"]["properties"]["kind"]["enum"]
    )
    text = describe(ctx)
    assert "w0:Personal" in text or "Personal" in text
    assert "p1-answer_slot-1" in text and "p1-cell_run" in text
    assert expand_refs(["w3-w5", "w9"]) == ["w3", "w4", "w5", "w9"]


def test_labels_are_rebuilt_from_the_document_words(ctx):
    answer = good_answer(ctx)
    answer["questions"][0]["label"] = "Something the model made up"
    elements, errors, warnings = validate(answer, ctx)
    assert not errors
    q1 = next(e for e in elements if e["id"] == "p1-q1")
    assert (
        q1["label"] == "Full name"
        and q1["text_source"] == "document"
        and q1["required"] is True
    )
    q2 = next(e for e in elements if e["id"] == "p1-q2")
    assert [o["label"] for o in q2["options"]] == ["Male", "Female"]
    assert any(e["type"] == "staff_only" for e in elements)
    assert any("not assigned" in w for w in warnings)  # the other slots were left out


def test_unknown_ids_and_bad_choices_are_errors(ctx):
    answer = good_answer(ctx)
    answer["questions"][0]["slot_refs"] = ["p1-answer_slot-999"]
    answer["questions"][1]["options"] = [{"refs": ids_of(ctx, "Male")}]
    answer["questions"].append({"id": "q3", "kind": "teleport", "label": "x"})
    _, errors, _ = validate(answer, ctx)
    assert any("unknown layout item" in e for e in errors)
    assert any("at least two options" in e for e in errors)
    assert any("unknown kind" in e for e in errors)


async def test_a_bad_answer_is_retried_once_with_its_errors(ctx):
    bad = {
        "sections": [],
        "questions": [{"id": "q1", "kind": "short_text", "label_refs": ["w99999"]}],
    }
    provider = FakeProvider([bad, good_answer(ctx)])
    result = await structure_page(provider, ctx, b"png")
    assert result.source == "model" and len(provider.calls) == 2
    assert "previous answer had these problems" in provider.calls[1]["prompt"]
    assert provider.calls[0]["image"] == b"png"


async def test_unusable_answers_fall_back_to_deterministic_structuring(ctx):
    bad = {"sections": [], "questions": [{"id": "q1", "kind": "nope"}]}
    result = await structure_page(FakeProvider([bad, bad]), ctx, None)
    assert result.source == "heuristic" and result.elements
    result = await structure_page(FakeProvider([RuntimeError("boom")]), ctx, None)
    assert result.source == "heuristic" and "provider error" in result.warnings[0]
    result = await structure_page(None, ctx, None)
    assert result.source == "heuristic" and result.warnings == ["no model available"]


def test_heuristic_finds_labels_choices_and_sections(ctx):
    elements = heuristic(ctx)
    questions = {e["label"]: e for e in elements if e["type"] == "question"}
    assert questions["Full name"]["kind"] == "short_text"
    assert questions["Date of birth"]["kind"] == "date"
    assert questions["Account number"]["kind"] == "char_cells"
    gender = questions["Gender"]
    assert gender["kind"] == "single_choice" and [
        o["label"] for o in gender["options"]
    ] == ["Male", "Female"]
    assert "Reviewed by" not in questions  # inside the staff-only region
    kinds = {e["type"] for e in elements}
    assert {"section", "statement", "staff_only"} <= kinds
    # ...where it is what staff fill in: compile makes it an internal field
    [staff] = [e for e in elements if e["type"] == "staff_only"]
    assert [(f["label"], f["kind"]) for f in staff["fields"]] == [
        ("Reviewed by", "short_text")
    ]


def test_model_staff_only_parts_carry_their_labelled_slots(ctx):
    elements, errors, _ = validate(good_answer(ctx), ctx)
    assert not errors
    [staff] = [e for e in elements if e["type"] == "staff_only"]
    assert staff["heading"] == "For office use only"
    assert [f["label"] for f in staff["fields"]] == ["Reviewed by"]
    # a slot the model made a question stays that question's
    answer = good_answer(ctx)
    slot = staff["fields"][0]["slot_refs"][0]
    answer["questions"].append(
        {"id": "q9", "kind": "short_text", "label": "Reviewer", "slot_refs": [slot]}
    )
    elements, _, _ = validate(answer, ctx)
    [staff] = [e for e in elements if e["type"] == "staff_only"]
    assert staff["fields"] == []


# --- OpenAI strict structured output ------------------------------------------

UNSUPPORTED_IN_STRICT = {
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "patternProperties",
    "propertyNames",
    "default",
    "allOf",
    "oneOf",
    "not",
    "if",
    "then",
    "else",
    "dependentRequired",
    "dependentSchemas",
}


def strict_problems(node, path="$"):
    """Where a JSON schema breaks OpenAI's strict mode rules: every object
    lists all its properties as required and allows no others, no unsupported
    keywords, and a nullable object is written with anyOf."""
    problems = []
    if not isinstance(node, dict):
        return [f"{path}: not a schema"]
    for key in UNSUPPORTED_IN_STRICT & set(node):
        problems.append(f"{path}: unsupported keyword {key}")
    types = node.get("type")
    types = [types] if isinstance(types, str) else list(types or [])
    if "object" in types:
        if len(types) > 1:
            problems.append(f"{path}: nullable object needs anyOf")
        properties = node.get("properties")
        if not isinstance(properties, dict) or not properties:
            problems.append(f"{path}: object without properties")
            properties = {}
        if node.get("additionalProperties") is not False:
            problems.append(f"{path}: additionalProperties must be false")
        if sorted(node.get("required") or []) != sorted(properties):
            problems.append(f"{path}: every property must be required")
        for name, child in properties.items():
            problems += strict_problems(child, f"{path}.{name}")
    if "array" in types:
        problems += strict_problems(node.get("items"), f"{path}[]")
    for i, option in enumerate(node.get("anyOf") or []):
        problems += strict_problems(option, f"{path}|{i}")
    if not types and "anyOf" not in node:
        problems.append(f"{path}: no type")
    return problems


def test_the_schema_follows_openai_strict_mode_rules():
    s = schema()
    assert s["type"] == "object"  # the root may not be an anyOf
    assert strict_problems(s) == []
    # the checker does catch what strict mode rejects
    assert strict_problems({"type": "object", "properties": {"a": {"type": "string"}}})
    assert strict_problems(
        {
            "type": "object",
            "properties": {"a": {"type": "string", "maxLength": 3}},
            "required": ["a"],
            "additionalProperties": False,
        }
    )


async def test_the_openai_provider_asks_for_strict_output():
    """A stand-in client: nothing is sent anywhere."""
    from types import SimpleNamespace

    from backend.app.services.openai_provider import OpenAIFormProvider

    sent = {}

    async def create(**kwargs):
        sent.update(kwargs)
        message = SimpleNamespace(content='{"sections": [], "questions": []}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    provider = OpenAIFormProvider(unsplash_service=None)
    provider._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    answer = await provider.analyze_page("system", "prompt", None, schema())
    assert answer == {"sections": [], "questions": []}
    json_schema = sent["response_format"]["json_schema"]
    assert json_schema["strict"] is True and json_schema["schema"] == schema()


async def test_nulls_in_a_strict_answer_count_as_absent(ctx):
    answer = good_answer(ctx)
    answer["statements"] = None
    answer["ignore"] = None
    answer["sections"][0].update(title=None, continues_previous=None)
    for question in answer["questions"]:
        for key in (
            "label",
            "help_refs",
            "follow_up_of",
            "applicant_index",
            "statement",
            "confidence",
        ):
            question[key] = None
    answer["questions"][0].update(options=None, required=None, section=None)
    answer["questions"][1]["options"][0].update(text=None, is_other=None)
    answer["staff_only"][0]["heading_refs"] = None
    elements, errors, _ = validate(answer, ctx)
    assert not errors
    q1 = next(e for e in elements if e["id"] == "p1-q1")
    assert q1["label"] == "Full name" and q1["required"] is None
    assert q1["section"] is None and q1["follow_up_of"] is None
    assert q1["confidence"] == 0.7
    q2 = next(e for e in elements if e["id"] == "p1-q2")
    assert [o["label"] for o in q2["options"]] == ["Male", "Female"]
    assert q2["options"][0]["is_other"] is False
    result = await structure_page(FakeProvider([answer]), ctx, None)
    assert result.source == "model"


async def test_pages_without_a_text_layer_take_text_from_the_image():
    ctx = page_context(None, None, 2, "scan")
    answer = {
        "sections": [{"id": "s1", "title": "Applicant"}],
        "questions": [{"id": "q1", "kind": "short_text", "label": "नाम"}],
    }
    result = await structure_page(FakeProvider([answer]), ctx, b"png")
    q = next(e for e in result.elements if e["type"] == "question")
    assert (
        result.source == "model" and q["label"] == "नाम" and q["text_source"] == "image"
    )

    # without vision the scan page cannot be structured at all
    class Blind(FakeProvider):
        supports_vision = False

    result = await structure_page(Blind([answer]), ctx, b"png")
    assert result.source == "none" and result.elements == []


def test_merge_joins_continued_sections_and_repeated_signatures():
    from backend.app.services.pdf_import.structuring import PageResult

    sig = lambda n: {
        "type": "question",
        "id": f"p{n}-sig",
        "kind": "signature",
        "label": "Applicant's signature",
        "applicant_index": None,
    }
    pages = [
        PageResult(
            1, "model", [{"type": "section", "id": "p1-s1", "title": "Details"}, sig(1)]
        ),
        PageResult(
            2,
            "model",
            [
                {
                    "type": "section",
                    "id": "p2-s1",
                    "title": "Details (continued)",
                    "continues_previous": True,
                },
                {
                    "type": "question",
                    "id": "p2-q1",
                    "kind": "short_text",
                    "label": "City",
                },
                sig(2),
            ],
        ),
    ]
    fdm = merge(pages)
    ids = [e["id"] for e in fdm["elements"]]
    assert "p2-s1" not in ids and ids.count("p1-sig") == 1 and "p2-sig" not in ids
    city = next(e for e in fdm["elements"] if e["id"] == "p2-q1")
    assert city["section"] == "p1-s1" and city["page"] == 2


@pytest.mark.parametrize(
    "malformed",
    [
        ["not", "an", "object"],
        {"questions": ["x"]},
        {"questions": "x"},
        {"sections": [1, 2]},
        {"questions": [{"id": "q1", "kind": "short_text", "label_refs": 5}]},
        {"questions": [{"id": "q1", "kind": "single_choice", "options": ["a", "b"]}]},
        {"questions": [{"id": "q1", "kind": "short_text", "label": {"x": 1}}]},
        {"staff_only": [{"refs": "p1-staff_region-1"}], "ignore": [{"id": 1}]},
        {
            "questions": [
                {"id": "q1", "kind": "short_text", "label_refs": ["w0-w999999"]}
            ]
        },
    ],
)
async def test_malformed_answers_fall_back_instead_of_failing_the_import(
    ctx, malformed
):
    result = await structure_page(FakeProvider([malformed, malformed]), ctx, None)
    assert result.source in ("model", "heuristic")
    for element in result.elements:
        assert isinstance(element.get("label", element.get("title", "")), str)


def test_model_text_and_refs_are_capped(ctx):
    answer = good_answer(ctx)
    answer["questions"][0]["label_refs"] = []
    answer["questions"][0]["label"] = "x" * 10000
    answer["questions"][1]["label_refs"] = ["w0-w2000"] * 50
    elements, _, _ = validate(answer, ctx)
    q1 = next(e for e in elements if e["id"] == "p1-q1")
    assert len(q1["label"]) <= 500
