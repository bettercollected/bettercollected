"""Compiling the FDM into the draft form: the redesign rules, the theme and
idempotence, all through the typed edit operations."""

import pytest

from backend.app.services.pdf_import.compile import (
    _contrast_with_white,
    _rgb,
    build_form,
    plan_form,
    theme_from,
)


def q(id_, kind, label, section="s1", **extra):
    return {
        "type": "question",
        "id": id_,
        "kind": kind,
        "label": label,
        "section": section,
        **extra,
    }


def fdm(*elements, sections=("s1",)):
    heads = [{"type": "section", "id": s, "title": f"Section {s}"} for s in sections]
    return {"version": 1, "elements": heads + list(elements)}


def titles(form):
    return [[f.title for f in page.properties.fields] for page in form.fields]


def field(form, title):
    return next(
        f for page in form.fields for f in page.properties.fields if f.title == title
    )


def test_other_option_gets_a_specify_field_shown_only_for_other():
    doc = fdm(
        q(
            "q1",
            "single_choice",
            "Occupation:",
            options=[
                {"label": "Salaried"},
                {"label": "Business"},
                {"label": "Other", "is_other": True},
            ],
        )
    )
    form, report = build_form(doc, {}, "T")
    occupation, specify = field(form, "Occupation"), field(form, "Please specify")
    assert [c.value for c in occupation.properties.choices] == [
        "Salaried",
        "Business",
        "Other",
    ]
    [condition] = (
        specify.properties.logic.conditions
        if hasattr(specify.properties, "logic") and specify.properties.logic
        else specify.logic.conditions
    )
    assert condition.field_id == occupation.id and condition.value == "Other"
    assert (
        report["logic_rules"] == 1
        and report["rules"]["other_option_gets_specify_field"] == 1
    )


def test_follow_ups_signatures_dates_and_thumbprints():
    doc = fdm(
        q("q1", "yes_no", "Have you been convicted?"),
        q(
            "q2",
            "long_text",
            "If yes, give details",
            follow_up_of={"question": "q1", "when": "yes"},
        ),
        q("q3", "date_pair_bs_ad", "Date of birth: B.S."),
        q("q4", "signature", "Applicant's signature"),
        q("q5", "thumbprint", "Right thumb"),
    )
    form, report = build_form(doc, {}, "T")
    all_titles = [t for page in titles(form) for t in page]
    assert "Date of birth (B.S.)" in all_titles and "Date of birth (A.D.)" in all_titles
    assert any(t.startswith("Full name, as your signature") for t in all_titles)
    assert report["dropped"][0]["reason"].startswith("Thumbprints")
    assert report["logic_rules"] == 1


def test_tables_staff_only_and_terms():
    long_terms = " ".join(["term"] * 200)
    doc = fdm(
        q(
            "q1",
            "table_fixed_rows",
            "Family",
            table={
                "header": ["Relation", "Name", "Account"],
                "row_labels": ["Father", "Mother"],
            },
        ),
        {
            "type": "staff_only",
            "id": "x1",
            "heading": "For office use only",
            "refs": ["p1"],
        },
        {
            "type": "statement",
            "id": "t1",
            "text": long_terms,
            "legal": True,
            "section": "s1",
        },
        q("q2", "signature", "Signature"),
    )
    form, report = build_form(doc, {}, "T")
    all_titles = [t for page in titles(form) for t in page]
    assert "Father – Name" in all_titles and "Mother – Account" in all_titles
    assert (
        report["interim"]
        and report["staff_only"][0]["heading"] == "For office use only"
    )
    assert any(page[0] == "Terms and declarations" for page in titles(form))
    assert "I have read and agree to the terms and declarations above." in all_titles


def test_long_sections_split():
    many = [q(f"q{i}", "short_text", f"Question {i}") for i in range(30)]
    form, report = build_form(fdm(*many), {}, "T")
    assert report["rules"]["long_section_split"] >= 2
    assert all(len(page.properties.fields) <= 14 for page in form.fields)


def test_tiny_sections_merge_into_the_previous_page():
    small = [q(f"q{i}", "short_text", f"Question {i}") for i in range(3)]
    tiny = [q("t1", "short_text", "Lonely", section="s2")]
    form, report = build_form(fdm(*small, *tiny, sections=("s1", "s2")), {}, "T")
    assert report["rules"]["tiny_section_merged"] == 1 and report["pages"] == 1
    assert titles(form)[0][-2:] == ["Section s2", "Lonely"]


def test_theme_is_the_brand_colour_made_readable():
    layout = {
        "pages": [
            {
                "primitives": [{"kind": "section_bar", "fill": "#ff0019"}] * 3
                + [{"kind": "section_bar", "fill": "#d9d9d9"}]
            }
        ]
    }
    theme = theme_from(layout)
    assert theme["accent"] == "#ff0019"
    assert _contrast_with_white(_rgb(theme["primary"])) >= 4.5
    assert (
        theme_from(
            {"pages": [{"primitives": [{"kind": "section_bar", "fill": "#a6a6a6"}]}]}
        )
        is None
    )


def test_compiling_twice_gives_the_same_form():
    doc = fdm(q("q1", "short_text", "Name"), q("q2", "email", "Email"))
    first, _ = build_form(doc, {}, "T")
    second, _ = build_form(doc, {}, "T")
    assert titles(first) == titles(second)


def test_plan_uses_verbatim_statements():
    plan = plan_form(
        fdm(
            {
                "type": "statement",
                "id": "t1",
                "text": "I declare that the information is true.",
                "legal": True,
                "section": "s1",
            }
        )
    )
    assert plan.pages[0].fields[1].spec == {
        "title": "I declare that the information is true.",
        "type": "text",
    }


def test_a_huge_document_model_is_capped_and_the_cuts_reported():
    from backend.app.services.pdf_import.compile import (
        MAX_CHOICES,
        MAX_FIELDS,
        MAX_HELP_CHARS,
    )

    many = [q(f"q{i}", "short_text", f"Question {i}") for i in range(MAX_FIELDS + 40)]
    choice = q(
        "c1",
        "single_choice",
        "Pick one",
        help="h" * 5000,
        options=[{"label": f"Option {i}"} for i in range(MAX_CHOICES + 30)],
    )
    form, report = build_form(fdm(choice, *many), {}, "T")
    count = sum(len(page.properties.fields) for page in form.fields)
    assert count <= MAX_FIELDS
    picked = field(form, "Pick one")
    assert len(picked.properties.choices) == MAX_CHOICES
    assert len(picked.description) <= MAX_HELP_CHARS
    reasons = " ".join(d.get("reason", "") for d in report["dropped"])
    assert "options were kept" in reasons and "cut at" in reasons


def test_stable_ids_repeat_for_the_same_document_model():
    from backend.app.services.pdf_import.compile import with_stable_ids

    doc = fdm(
        q("q1", "yes_no", "Any other account?"),
        q(
            "q2",
            "short_text",
            "Which bank?",
            follow_up_of={"question": "q1", "when": "yes"},
        ),
    )
    ids = []
    for _ in range(2):
        form, _ = build_form(doc, {}, "T")
        form = with_stable_ids(form, "import-1")
        ids.append(
            [f.id for page in form.fields for f in [page, *page.properties.fields]]
        )
    assert ids[0] == ids[1]
    other, _ = build_form(doc, {}, "T")
    assert [f.id for f in with_stable_ids(other, "import-2").fields] != ids[0][:1]
