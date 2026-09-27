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
    assert report["rules"]["fixed_table_to_fields"] == 1 and "interim" not in report
    # a staff-only part without labelled answer places is only listed
    assert report["staff_only"][0]["heading"] == "For office use only"
    assert report["staff_only"][0]["internal_fields"] == 0
    assert report["rules"]["staff_only_listed"] == 1
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


# --- staff-only parts become internal fields (D5, D10) --------------------------


def staff(*fields, heading="For office use only", id_="x1"):
    return {
        "type": "staff_only",
        "id": id_,
        "heading": heading,
        "refs": ["p1-staff_region-1"],
        "fields": list(fields),
    }


def test_staff_only_parts_become_internal_fields_on_a_page_of_their_own():
    from backend.app.services.internal_fields import (
        INTERNAL_CAPABLE_TYPES,
        ensure_no_internal_logic,
        strip_internal_fields,
    )

    doc = fdm(
        q("q1", "short_text", "Full name"),
        staff(
            {"kind": "short_text", "label": "Reviewed by:"},
            {"kind": "date", "label": "Date received"},
            {
                "kind": "single_choice",
                "label": "Decision",
                "options": [
                    {"label": "Approved"},
                    {"label": "Rejected"},
                    {"label": "Other", "is_other": True},
                ],
            },
            {"kind": "signature", "label": "Checked by"},
            {"kind": "thumbprint", "label": "Thumb"},
        ),
    )
    form, report = build_form(doc, {}, "T")
    *respondent_pages, office = form.fields
    assert [f.title for f in office.properties.fields] == [
        "Reviewed by",
        "Date received",
        "Decision",
        "Checked by",
    ]
    assert all(f.internal for f in office.properties.fields)
    assert {f.type.value for f in office.properties.fields} <= INTERNAL_CAPABLE_TYPES
    assert not any(
        f.internal for page in respondent_pages for f in page.properties.fields
    )
    # no "Please specify" for a staff choice: its logic would read an internal field
    assert all(
        f.properties.logic is None
        for page in form.fields
        for f in page.properties.fields
    )
    ensure_no_internal_logic(form)
    assert report["internal_fields"] == 4 and not report["failures"]
    assert report["staff_only"][0]["internal_fields"] == 4
    assert report["rules"]["staff_only_to_internal_fields"] == 4
    assert "staff_only_listed" not in report["rules"]
    assert any(d.get("label") == "Thumb" for d in report["dropped"])
    # respondents never see the page
    shown = strip_internal_fields(form.model_copy(deep=True))
    assert [p.id for p in shown.fields] == [p.id for p in respondent_pages]


def test_many_staff_fields_split_over_internal_pages_after_the_terms():
    doc = fdm(
        q("q1", "short_text", "Full name"),
        {
            "type": "statement",
            "id": "t1",
            "text": " ".join(["term"] * 200),
            "legal": True,
            "section": "s1",
        },
        staff(*[{"kind": "short_text", "label": f"Code {i}"} for i in range(20)]),
    )
    form, report = build_form(doc, {}, "T")
    assert titles(form)[0][0] == "Terms and declarations"  # before the form's last page
    internal_pages = [
        page for page in form.fields if all(f.internal for f in page.properties.fields)
    ]
    assert len(internal_pages) == 2
    assert [p.id for p in form.fields[-2:]] == [p.id for p in internal_pages]
    assert report["internal_fields"] == 20


# --- tables and joint applicants become repeating groups (D7) --------------------


def groups(form):
    return [
        f
        for page in form.fields
        for f in page.properties.fields
        if f.type.value == "group"
    ]


def test_an_open_row_table_becomes_a_repeating_group():
    from common.models.standard_form import REPEAT_CHILD_FIELD_TYPES

    doc = fdm(
        q(
            "q1",
            "table_open_rows",
            "Family members",
            table={"header": ["Name", "Relation", "Date of birth"], "rows": 4},
        ),
        q(
            "q2",
            "table_open_rows",
            "Name / Bank",
            required=True,
            table={"header": ["Name", "Bank"], "rows": 80},
        ),
        q("q3", "table_open_rows", "Previous addresses", table={"header": []}),
    )
    form, report = build_form(doc, {}, "T")
    family, banks, addresses = groups(form)
    assert family.title == "Family members"
    assert [c.title for c in family.properties.fields] == [
        "Name",
        "Relation",
        "Date of birth",
    ]
    assert [c.type.value for c in family.properties.fields] == [
        "short_text",
        "short_text",
        "date",
    ]
    repeat = family.properties.repeat
    assert (repeat.min_items, repeat.max_items) == (0, 3)
    assert repeat.item_label == "Family members"
    # required: at least one row; more rows than a group allows: capped at 50;
    # a label made of the header: the item is named after the first column
    assert banks.properties.repeat.min_items == 1
    assert banks.properties.repeat.max_items == 50
    assert banks.properties.repeat.item_label == "Name"
    # no header: one question named after the table, the default row count
    assert [c.title for c in addresses.properties.fields] == ["Previous addresses"]
    assert addresses.properties.repeat.max_items == 5
    for group in (family, banks, addresses):
        for child in group.properties.fields:
            assert child.type.value in REPEAT_CHILD_FIELD_TYPES and not child.internal
    assert report["rules"]["open_table_to_repeating_group"] == 3
    assert report["repeating_groups"] == 3 and not report["failures"]
    assert "table_to_rows_of_fields" not in report["rules"]


def applicant(index, occupation_options=("Salaried", "Business", "Other")):
    return [
        q(f"a{index}-name", "short_text", "Name", applicant_index=index),
        q(
            f"a{index}-job",
            "single_choice",
            "Occupation",
            applicant_index=index,
            options=[
                {"label": o, "is_other": o == "Other"} for o in occupation_options
            ],
        ),
        q(
            f"a{index}-employer",
            "short_text",
            "Employer",
            applicant_index=index,
            follow_up_of={"question": f"a{index}-job", "when": "Salaried"},
        ),
        q(f"a{index}-photo", "image", "Photo", applicant_index=index),
        q(f"a{index}-sign", "signature", "Signature", applicant_index=index),
    ]


def test_joint_applicant_blocks_become_one_repeating_group():
    doc = fdm(*applicant(1), *applicant(2), *applicant(3))
    form, report = build_form(doc, {}, "T")
    [group] = groups(form)
    repeat = group.properties.repeat
    assert (repeat.min_items, repeat.max_items) == (1, 3)
    assert repeat.item_label == "Applicant"
    by_title = {c.title: c for c in group.properties.fields}
    assert list(by_title)[:4] == ["Name", "Occupation", "Please specify", "Employer"]
    assert any(t.startswith("Full name, as your signature") for t in by_title)
    # item-scoped logic: siblings in the same group
    specify, employer = by_title["Please specify"], by_title["Employer"]
    assert specify.properties.logic.conditions[0].field_id == by_title["Occupation"].id
    assert employer.properties.logic.conditions[0].value == "Salaried"
    # photos cannot repeat: they stay per applicant, prefixed as before
    all_titles = [t for page in titles(form) for t in page]
    assert "Photo" in all_titles and "Applicant 2: Photo" in all_titles
    assert "Applicant 2: Name" not in all_titles
    assert report["rules"]["applicant_blocks_to_repeating_group"] == 1
    assert report["logic_rules"] == 2 and not report["failures"]


def test_applicant_blocks_that_differ_keep_their_prefixes():
    doc = fdm(*applicant(1), q("a2-name", "short_text", "Name", applicant_index=2))
    form, report = build_form(doc, {}, "T")
    assert not groups(form)
    all_titles = [t for page in titles(form) for t in page]
    assert "Applicant 2: Name" in all_titles
    assert report["rules"]["applicant_blocks_prefixed"] >= 1


def test_stable_ids_keep_groups_and_their_logic_consistent():
    from backend.app.services.pdf_import.compile import with_stable_ids

    doc = fdm(
        *applicant(1),
        *applicant(2),
        q("t1", "table_open_rows", "Loans", table={"header": ["Bank"], "rows": 3}),
        staff({"kind": "short_text", "label": "Reviewed by"}),
    )
    dumps = []
    for _ in range(2):
        form, _ = build_form(doc, {}, "T")
        form = with_stable_ids(form, "import-1")
        dumps.append(form.model_dump(mode="json"))
        for group in groups(form):
            sibling_ids = {c.id for c in group.properties.fields}
            for child in group.properties.fields:
                logic = child.properties.logic
                for condition in logic.conditions if logic else []:
                    assert condition.field_id in sibling_ids
    assert dumps[0] == dumps[1]
