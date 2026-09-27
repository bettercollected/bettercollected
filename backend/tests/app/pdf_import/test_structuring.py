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
