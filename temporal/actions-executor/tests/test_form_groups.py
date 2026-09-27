"""Repeating groups in the answer extraction used by e-mails, chat
integrations and Google Sheets."""

from utilities.form import (
    column_letter,
    get_group_tables,
    get_questions_and_answers,
    sheet_title_for,
)


def form_with_group(max_items=2, export_layout=None):
    repeat = {"min_items": 1, "max_items": max_items, "item_label": "Applicant"}
    if export_layout:
        repeat["export_layout"] = export_layout
    return {
        "form_id": "f1",
        "fields": [
            {
                "id": "s1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "email", "type": "email", "title": "Contact e-mail"},
                        {
                            "id": "g",
                            "type": "group",
                            "title": "Applicants",
                            "properties": {
                                "repeat": repeat,
                                "fields": [
                                    {
                                        "id": "name",
                                        "type": "short_text",
                                        "title": "Name",
                                    },
                                    {
                                        "id": "income",
                                        "type": "number",
                                        "title": "Income",
                                    },
                                ],
                            },
                        },
                    ]
                },
            }
        ],
    }


RESPONSE = {
    "response_id": "r1",
    "answers": {
        "email": {"type": "email", "email": "a@example.org"},
        "g": {
            "type": "group",
            "items": [
                {
                    "name": {"type": "text", "text": "Sita"},
                    "income": {"type": "number", "number": 10},
                },
                {"name": {"type": "text", "text": "Ram"}},
            ],
        },
    },
}


def titles_and_answers(entries):
    return [(e["title"], e["answer"]) for e in entries]


def test_mail_style_extraction_lists_actual_items():
    entries = get_questions_and_answers(form_with_group(max_items=4), RESPONSE)
    assert titles_and_answers(entries) == [
        ("Contact e-mail", "a@example.org"),
        ("Applicant 1 – Name", "Sita"),
        ("Applicant 1 – Income", 10),
        ("Applicant 2 – Name", "Ram"),
        ("Applicant 2 – Income", ""),
    ]


def test_sheet_columns_are_fixed_to_the_maximum():
    entries = get_questions_and_answers(
        form_with_group(max_items=3), RESPONSE, fixed_columns=True
    )
    assert [e["title"] for e in entries][-2:] == [
        "Applicant 3 – Name",
        "Applicant 3 – Income",
    ]
    assert len(entries) == 1 + 3 * 2


def test_large_groups_go_to_a_separate_table():
    form = form_with_group(max_items=10)
    entries = get_questions_and_answers(form, RESPONSE, fixed_columns=True)
    assert titles_and_answers(entries) == [
        ("Contact e-mail", "a@example.org"),
        ("Applicants (Applicant count)", 2),
        ("Response ID", "r1"),
    ]
    [table] = get_group_tables(form, RESPONSE)
    assert table["headers"] == ["Response ID", "Applicant", "Name", "Income"]
    assert table["rows"] == [["r1", 1, "Sita", 10], ["r1", 2, "Ram", ""]]


def test_creator_can_override_the_layout():
    assert get_group_tables(
        form_with_group(max_items=2, export_layout="rows"), RESPONSE
    )
    assert not get_group_tables(
        form_with_group(max_items=10, export_layout="columns"), RESPONSE
    )


def test_camel_case_settings_and_old_responses():
    form = form_with_group()
    group = form["fields"][0]["properties"]["fields"][1]
    group["properties"]["repeat"] = {"maxItems": 1, "itemLabel": "Person"}
    entries = get_questions_and_answers(form, {"answers": {}}, fixed_columns=True)
    assert [e["title"] for e in entries] == [
        "Contact e-mail",
        "Person 1 – Name",
        "Person 1 – Income",
    ]


def test_column_letters_and_sheet_titles():
    assert [column_letter(n) for n in (1, 26, 27, 52, 53)] == [
        "A",
        "Z",
        "AA",
        "AZ",
        "BA",
    ]
    assert sheet_title_for("Family: members/[all]") == "Family  members  all"


def test_group_tabs_never_share_a_name():
    form = form_with_group(max_items=10)
    page = form["fields"][0]["properties"]["fields"]
    long_title = "x" * 120
    first = page[1]
    first["title"] = long_title
    page.append({**first, "id": "g2", "title": long_title + " (different tail)"})
    page.append({**first, "id": "g3", "title": long_title.upper()})
    titles = [t["sheet_title"] for t in get_group_tables(form, RESPONSE)]
    assert len(titles) == 3
    assert len({t.lower() for t in titles}) == 3
    assert all(len(t) <= 100 for t in titles)
    assert titles[0] == "x" * 100
    assert titles[1].endswith("(g2)")
    # Stable: the same form always yields the same names.
    assert titles == [t["sheet_title"] for t in get_group_tables(form, RESPONSE)]
