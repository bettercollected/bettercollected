"""Inputs of the golden tests of ``builtin_actions.qa``.

Every case is plain JSON data. ``battery.run`` feeds them to a module that has
the executor's ``utilities.form`` functions (the port, or the executor's own
file when the golden output is made) and collects the results.
"""

# ---------------------------------------------------------------------------
# one answer per question type: (name, field, answer)
# ---------------------------------------------------------------------------

UUID_A = "11111111-2222-3333-4444-555555555555"
UUID_B = "66666666-7777-8888-9999-000000000000"

CHOICES = [
    {"id": "c1", "value": "Red"},
    {"id": "c2", "value": "Green"},
    {"id": "c3", "value": ""},
    {"id": "c4"},
]

ANSWER_CASES = [
    ("number", {"id": "f", "type": "number"}, {"number": 3}),
    ("number zero", {"id": "f", "type": "number"}, {"number": 0}),
    ("number missing", {"id": "f", "type": "number"}, {}),
    ("rating", {"id": "f", "type": "rating"}, {"number": 4}),
    ("linear rating", {"id": "f", "type": "linear_rating"}, {"number": 9}),
    ("input rating", {"id": "f", "type": "input_rating"}, {"number": 2}),
    ("input number", {"id": "f", "type": "input_number"}, {"number": 2.5}),
    ("short text", {"id": "f", "type": "short_text"}, {"text": "Ada"}),
    ("long text", {"id": "f", "type": "long_text"}, {"text": "a\nb"}),
    ("text", {"id": "f", "type": "text"}, {"text": "x"}),
    ("input short text", {"id": "f", "type": "input_short_text"}, {"text": "s"}),
    ("input long text", {"id": "f", "type": "input_long_text"}, {"text": "l"}),
    ("text missing", {"id": "f", "type": "short_text"}, {}),
    ("url", {"id": "f", "type": "url"}, {"url": "https://example.org/a?b=c"}),
    ("input link", {"id": "f", "type": "input_link"}, {"url": "https://x.example"}),
    ("email", {"id": "f", "type": "email"}, {"email": "a@example.org"}),
    ("input email", {"id": "f", "type": "input_email"}, {"email": "b@example.org"}),
    ("date", {"id": "f", "type": "date"}, {"date": "2026-11-02"}),
    ("day", {"id": "f", "type": "day"}, {"date": "2026-11-03"}),
    ("input date", {"id": "f", "type": "input_date"}, {"date": "2026-11-04"}),
    ("time", {"id": "f", "type": "time"}, {"time": "13:45"}),
    (
        "currency",
        {"id": "f", "type": "currency"},
        {"currency": {"code": "EUR", "amount": "12.50"}},
    ),
    ("currency without code", {"id": "f", "type": "currency"}, {"currency": {"amount": "7"}}),
    ("currency without amount", {"id": "f", "type": "currency"}, {"currency": {"code": "EUR"}}),
    ("currency missing", {"id": "f", "type": "currency"}, {}),
    (
        "date range",
        {"id": "f", "type": "date_range"},
        {"date_range": {"start": "2026-01-01", "end": "2026-01-09"}},
    ),
    ("date range open end", {"id": "f", "type": "date_range"}, {"date_range": {"start": "2026-01-01"}}),
    ("date range open start", {"id": "f", "type": "date_range"}, {"date_range": {"end": "2026-01-09"}}),
    ("date range empty", {"id": "f", "type": "date_range"}, {}),
    ("tags", {"id": "f", "type": "tags"}, {"tags": ["one", "two", 3]}),
    ("tags not a list", {"id": "f", "type": "tags"}, {"tags": "one"}),
    ("tags empty", {"id": "f", "type": "tags"}, {"tags": []}),
    (
        "address NL",
        {"id": "f", "type": "address"},
        {
            "address": {
                "street": " Keizersgracht ",
                "house_number": "12",
                "house_number_addition": "B",
                "postcode": "1015 CJ",
                "city": "Amsterdam",
                "country": "NL",
            }
        },
    ),
    (
        "address foreign",
        {"id": "f", "type": "address"},
        {
            "address": {
                "street": "Rue X",
                "house_number": "3",
                "postcode": "75001",
                "city": "Paris",
                "country": "FR",
            }
        },
    ),
    (
        "address only country",
        {"id": "f", "type": "address"},
        {"address": {"country": "BE"}},
    ),
    ("address not a dict", {"id": "f", "type": "address"}, {"address": "street 1"}),
    ("address missing", {"id": "f", "type": "address"}, {}),
    ("yes", {"id": "f", "type": "yes_no"}, {"boolean": True}),
    ("no", {"id": "f", "type": "yes_no"}, {"boolean": False}),
    ("yes no unanswered", {"id": "f", "type": "yes_no"}, {}),
    (
        "dropdown single",
        {"id": "f", "type": "dropdown", "properties": {"choices": CHOICES}},
        {"choice": {"value": "c2"}},
    ),
    (
        "dropdown single other",
        {"id": "f", "type": "dropdown", "properties": {"choices": CHOICES}},
        {"choice": {"value": "c1", "other": "Purple"}},
    ),
    (
        "dropdown other only",
        {"id": "f", "type": "dropdown", "properties": {"choices": CHOICES}},
        {"choice": {"other": "Purple"}},
    ),
    (
        "choice with empty or missing value",
        {
            "id": "f",
            "type": "multiple_choice",
            "properties": {"choices": CHOICES, "allow_multiple_selection": True},
        },
        {"choices": {"values": ["c3", "c4", "c1"]}},
    ),
    (
        "multiple choice many",
        {
            "id": "f",
            "type": "multiple_choice",
            "properties": {"choices": CHOICES, "allow_multiple_selection": True},
        },
        {"choices": {"values": ["c2", "c1"], "other": "Else"}},
    ),
    (
        "multiple choice none",
        {
            "id": "f",
            "type": "multiple_choice",
            "properties": {"choices": CHOICES, "allow_multiple_selection": True},
        },
        {"choices": {"values": []}},
    ),
    (
        "multiple choice single selection",
        {"id": "f", "type": "multiple_choice", "properties": {"choices": CHOICES}},
        {"choice": {"value": "c1"}},
    ),
    (
        "sourced single",
        {"id": "f", "type": "dropdown", "properties": {"option_source": {"kind": "list"}}},
        {"choice": {"value": "li1", "label": "Alice Example"}},
    ),
    (
        "sourced single other",
        {"id": "f", "type": "dropdown", "properties": {"option_source": {"kind": "list"}}},
        {"choice": {"value": "li1", "label": "Alice", "other": "Else"}},
    ),
    (
        "sourced many",
        {
            "id": "f",
            "type": "multiple_choice",
            "properties": {"option_source": {"kind": "form_answers"}, "allow_multiple_selection": True},
        },
        {"choices": {"values": ["a2", "a1", "a3"], "labels": {"a1": "Bob", "a2": "Carol", "a3": ""}, "other": "Dan"}},
    ),
    (
        "sourced unanswered",
        {"id": "f", "type": "dropdown", "properties": {"option_source": {"kind": "list"}}},
        {},
    ),
    (
        "static question ignores forged labels",
        {"id": "f", "type": "dropdown", "properties": {"choices": [{"id": "c1", "value": "Red"}]}},
        {"choice": {"value": "c1", "label": "Forged"}},
    ),
    ("phone", {"id": "f", "type": "phone_number"}, {"phone_number": "+31 6 12345678"}),
    ("input phone", {"id": "f", "type": "input_phone_number"}, {"phone_number": "0612345678"}),
    (
        "input multiple choice",
        {"id": "f", "type": "input_multiple_choice", "properties": {"choices": CHOICES}},
        {"choice": {"value": "c2"}},
    ),
    (
        "input dropdown unknown",
        {"id": "f", "type": "input_dropdown", "properties": {"choices": CHOICES}},
        {"choice": {"value": "nope"}},
    ),
    (
        "input checkboxes by value",
        {"id": "f", "type": "input_checkboxes", "properties": {"choices": CHOICES[:3]}},
        {"choices": {"values": ["Green", "Red"]}},
    ),
    (
        "input checkboxes by id",
        {
            "id": "f",
            "type": "input_checkboxes",
            "properties": {"choices": [{"id": UUID_A, "value": "One"}, {"id": UUID_B, "value": "Two"}]},
        },
        {"choices": {"values": [UUID_B, UUID_A]}},
    ),
    (
        "input checkboxes empty",
        {"id": "f", "type": "input_checkboxes", "properties": {"choices": CHOICES[:3]}},
        {"choices": {"values": []}},
    ),
    (
        "input ranking",
        {"id": "f", "type": "input_ranking"},
        {"choices": {"values": [{"value": "First"}, {"value": "Second"}]}},
    ),
    ("file upload", {"id": "f", "type": "file_upload"}, {"file_metadata": {"name": "cv.pdf", "size": 10}}),
    ("input file upload", {"id": "f", "type": "input_file_upload"}, {"file_metadata": {"name": "a.png"}}),
    ("file upload missing", {"id": "f", "type": "file_upload"}, {}),
    ("signature typed", {"id": "f", "type": "signature"}, {"signature": {"method": "typed", "name": "Ada Lovelace"}}),
    ("signature drawn", {"id": "f", "type": "signature"}, {"signature": {"method": "drawn", "image": "data:image/png;base64,AAAA"}}),
    ("signature empty", {"id": "f", "type": "signature"}, {"signature": {"method": "other"}}),
    ("signature missing", {"id": "f", "type": "signature"}, {}),
    ("calculated number", {"id": "f", "type": "calculated", "properties": {"format": {"style": "currency", "decimals": 2}}}, {"number": 1234.5}),
    ("calculated text", {"id": "f", "type": "calculated"}, {"text": "adult"}),
    ("calculated boolean", {"id": "f", "type": "calculated"}, {"boolean": False}),
    ("calculated none", {"id": "f", "type": "calculated"}, {}),
    ("unknown type", {"id": "f", "type": "hologram"}, {"text": "x"}),
]

# (answer, format) for format_calculated_value
CALCULATED_FORMATS = [
    ({"number": 0.256}, {"style": "percent"}),
    ({"number": 0.256}, {"style": "percent", "decimals": 1}),
    ({"number": -2.5}, {"style": "currency"}),
    ({"number": 12}, {"style": "currency", "currency": "USD"}),
    ({"number": 12}, {"style": "currency", "currency": "USD", "decimals": 0}),
    ({"number": 1234.5678}, {"style": "number", "decimals": 2}),
    ({"number": 1234.5}, None),
    ({"number": 1234.5}, "not a dict"),
    ({"number": 1000000}, {"style": "number"}),
    ({"number": 2.675}, {"style": "number", "decimals": 2}),
    ({"number": 12}, {"style": "text"}),
    ({"number": 12.5}, {"style": "text"}),
    ({"number": 0}, {"style": "number"}),
    ({"boolean": True}, None),
    ({"boolean": False}, None),
    ({"text": "adult"}, {"style": "currency"}),
    ({"type": "text"}, None),
    ({}, None),
    ("not a dict", None),
    ({"number": "12.5"}, {"style": "number", "decimals": 1}),
    ({"number": "abc"}, {"style": "number"}),
]

ADDRESS_VALUES = [
    None,
    "a string",
    {},
    {"street": "Main", "house_number": "1"},
    {"postcode": "1234 AB", "city": "Town", "country": "NL"},
    {"postcode": "1234 AB", "city": "Town", "country": "DE"},
    {"country": "DE"},
    {"street": 5, "city": " X "},
]

FORMULA_STRINGS = [
    '=HYPERLINK("x")', "+1", "-2", "@SUM(A1)", "\tx", "\rx", " =1+1", " +1",
    "　-2", "﻿@x", "\n =1", " =1", "\x1f=1", "-5", "plain", "", "a =1",
    "x\n=1", "2026-09-27", "=", " ", 5, -5, 3.5, None, True,
]

COLUMN_COUNTS = [0, 1, 2, 25, 26, 27, 52, 53, 702, 703, 18278]

SHEET_TITLES = [
    "Family: members/[all]", "", None, "x" * 120, "It's", "A\\B*C?", "  spaced  ", "[]", 7,
]

# (title, field id) sequences through one shared ``used`` set
UNIQUE_SHEET_TITLE_RUNS = [
    [("Applicants", "g1"), ("applicants", "g2"), ("APPLICANTS", "g3"), ("Applicants", "g4")],
    [("x" * 120, "g1abcdefgh"), ("x" * 120, "g2abcdefgh"), ("X" * 120, "g3abcdefgh")],
    [("", "a"), (None, "b")],
]

# ---------------------------------------------------------------------------
# whole forms
# ---------------------------------------------------------------------------


def _slide(*fields, slide_id="s"):
    return {"id": slide_id, "type": "slide", "properties": {"fields": list(fields)}}


def _doc(text):
    """A rich-text title as the builder stores it."""
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def _group(max_items=2, layout=None, label="Applicant", gid="g", title="Applicants", camel=False):
    repeat = (
        {"minItems": 1, "maxItems": max_items, "itemLabel": label}
        if camel
        else {"min_items": 1, "max_items": max_items, "item_label": label}
    )
    if layout:
        repeat["exportLayout" if camel else "export_layout"] = layout
    return {
        "id": gid,
        "type": "group",
        "title": title,
        "properties": {
            "repeat": repeat,
            "fields": [
                {"id": "name", "type": "short_text", "title": "Name"},
                {"id": "income", "type": "number", "title": "Income"},
                {"id": "note", "type": "text", "title": "ignored static text"},
                {"id": "secret", "type": "short_text", "title": "office", "internal": True},
            ],
        },
    }


GROUP_ANSWER = {
    "type": "group",
    "items": [
        {"name": {"type": "text", "text": "Sita"}, "income": {"type": "number", "number": 10}},
        {"name": {"type": "text", "text": "Ram"}},
    ],
}

FORM_CASES = [
    {
        "name": "every kind of title",
        "form": {
            "form_id": "f1",
            "fields": [
                _slide(
                    {"id": "a", "type": "short_text", "title": "Plain title"},
                    {"id": "b", "type": "short_text", "title": _doc("Rich title")},
                    {"id": "c", "type": "short_text", "title": {"type": "doc", "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Two "}, {"type": "text", "text": "parts"}]},
                        {"type": "paragraph", "content": [{"type": "text", "text": "paragraphs"}]},
                    ]}},
                    {"id": "d", "type": "email"},
                    {"id": "e", "type": "number", "title": ""},
                    {"id": "f", "type": "dropdown", "title": None, "properties": {"choices": CHOICES}},
                    {"id": "g", "type": "hologram", "title": ""},
                    {"id": "h", "type": "yes_no"},
                    {"id": "i", "type": "signature"},
                    {"id": "j", "type": "address"},
                    {"id": "img", "type": "image_content", "title": "skipped"},
                    {"id": "vid", "type": "video_content", "title": "skipped"},
                    {"id": "txt", "type": "text", "title": "skipped"},
                ),
                {"id": "empty-slide", "type": "slide"},
                {"id": "no-fields", "type": "slide", "properties": {}},
            ],
        },
        "response": {
            "response_id": "r1",
            "answers": {
                "a": {"text": "A"}, "b": {"text": "B"}, "c": {"text": "C"}, "d": {"email": "d@example.org"},
                "e": {"number": 5}, "f": {"choice": {"value": "c1"}}, "g": {}, "h": {"boolean": True},
                "i": {"signature": {"method": "typed", "name": "Never Shown"}},
                "j": {"address": {"street": "S", "house_number": "1", "postcode": "1000 AA", "city": "C", "country": "NL"}},
            },
        },
    },
    {
        "name": "internal and hidden fields",
        "form": {
            "fields": [
                _slide(
                    {"id": "name", "type": "short_text", "title": "Your name"},
                    {"id": "risk", "type": "short_text", "title": "Risk rating", "internal": True},
                    {"id": "verdict", "type": "multiple_choice", "title": "Reviewer verdict", "internal": True,
                     "properties": {"choices": [{"id": "c1", "value": "Ok"}]}},
                    {"id": "qty", "type": "number", "title": "Quantity"},
                    {"id": "total", "type": "calculated", "title": "Total",
                     "properties": {"format": {"style": "currency", "decimals": 2}}},
                    {"id": "score", "type": "calculated", "title": "Risk score",
                     "properties": {"hiddenFromRespondents": True}},
                    {"id": "score2", "type": "calculated", "title": "Second score",
                     "properties": {"hidden_from_respondents": True}},
                    {"id": "plain-calc", "type": "calculated", "title": "Plain",
                     "properties": {"hidden_from_respondents": False}},
                    {"id": "no-props", "type": "calculated", "title": "No properties"},
                )
            ]
        },
        "response": {
            "response_id": "r2",
            "answers": {
                "name": {"text": "Ada"}, "risk": {"text": "high"}, "verdict": {"choice": {"value": "c1"}},
                "qty": {"type": "number", "number": 3}, "total": {"type": "number", "number": 1234.5},
                "score": {"type": "number", "number": 7}, "score2": {"number": 8},
                "plain-calc": {"boolean": True}, "no-props": {"text": "t"},
            },
        },
    },
    {
        "name": "matrix",
        "form": {
            "fields": [
                _slide(
                    {"id": "m", "type": "matrix", "title": "Satisfaction",
                     "properties": {"fields": [
                         {"id": "r1", "type": "linear_rating", "title": "Service", "index": 0},
                         {"id": "r2", "type": "linear_rating", "title": "", "index": 1},
                         {"id": "r3", "type": "linear_rating", "index": 2},
                         {"id": "r4", "type": "linear_rating", "title": _doc("Rich row"), "index": 3},
                     ]}},
                    {"id": "after", "type": "short_text", "title": "After"},
                )
            ]
        },
        "response": {
            "response_id": "r3",
            "answers": {
                "r1": {"number": 8}, "r2": {"number": 6}, "r3": {"number": 1}, "r4": {"number": 2},
                "after": {"text": "ok"},
            },
        },
    },
    {
        "name": "choices of every kind in one form",
        "form": {
            "fields": [
                _slide(
                    {"id": "one", "type": "dropdown", "title": "One", "properties": {"choices": CHOICES}},
                    {"id": "many", "type": "multiple_choice", "title": "Many",
                     "properties": {"choices": CHOICES, "allow_multiple_selection": True}},
                    {"id": "src", "type": "dropdown", "title": "Sourced", "properties": {"option_source": {"kind": "list"}}},
                    {"id": "srcmany", "type": "multiple_choice", "title": "Sourced many",
                     "properties": {"option_source": {"kind": "form_answers"}, "allow_multiple_selection": True}},
                    {"id": "tags", "type": "tags", "title": "Tags"},
                    {"id": "dr", "type": "date_range", "title": "Dates"},
                    {"id": "money", "type": "currency", "title": "Money"},
                    {"id": "t", "type": "time", "title": "Time"},
                    {"id": "dy", "type": "day", "title": "Day"},
                )
            ]
        },
        "response": {
            "response_id": "r4",
            "answers": {
                "one": {"choice": {"value": "c2", "other": "x"}},
                "many": {"choices": {"values": ["c1", "c2"], "other": "Else"}},
                "src": {"choice": {"value": "li1", "label": "Alice Example"}},
                "srcmany": {"choices": {"values": ["a2", "a1"], "labels": {"a1": "Bob", "a2": "Carol"}}},
                "tags": {"tags": ["x", "y"]},
                "dr": {"date_range": {"start": "2026-01-01", "end": "2026-02-01"}},
                "money": {"currency": {"code": "USD", "amount": "9.99"}},
                "t": {"time": "09:00"}, "dy": {"date": "2026-03-04"},
            },
        },
    },
    {
        "name": "group columns layout",
        "form": {"form_id": "f1", "fields": [_slide({"id": "email", "type": "email", "title": "Contact e-mail"}, _group(max_items=4))]},
        "response": {"response_id": "r5", "answers": {"email": {"email": "a@example.org"}, "g": GROUP_ANSWER}},
    },
    {
        "name": "group rows layout (large)",
        "form": {"form_id": "f1", "fields": [_slide({"id": "email", "type": "email", "title": "Contact e-mail"}, _group(max_items=10))]},
        "response": {"response_id": "r6", "answers": {"email": {"email": "a@example.org"}, "g": GROUP_ANSWER}},
    },
    {
        "name": "group layout overrides",
        "form": {"form_id": "f1", "fields": [_slide(
            _group(max_items=2, layout="rows", gid="small-rows", title="Small as rows"),
            _group(max_items=10, layout="columns", gid="large-cols", title="Large as columns"),
            _group(max_items=3, layout="nonsense", gid="bad-layout", title="Bad layout"),
        )]},
        "response": {"response_id": "r7", "answers": {"small-rows": GROUP_ANSWER, "large-cols": GROUP_ANSWER, "bad-layout": GROUP_ANSWER}},
    },
    {
        "name": "group camelCase settings and no answers",
        "form": {"fields": [_slide({"id": "email", "type": "email", "title": "Contact e-mail"}, _group(max_items=1, label="Person", camel=True))]},
        "response": {"answers": {}},
    },
    {
        "name": "group camelCase rows",
        "form": {"fields": [_slide(_group(max_items=9, label="Person", camel=True))]},
        "response": {"response_id": "r8", "answers": {"g": GROUP_ANSWER}},
    },
    {
        "name": "group malformed answers",
        "form": {"fields": [_slide(_group(max_items=10), _group(max_items=2, gid="g2", title="Second"))]},
        "response": {"response_id": "r9", "answers": {
            "g": {"type": "group", "items": [{"name": "plain string"}, "not a dict", None, {"name": {"text": "ok"}, "income": "bad"}]},
            "g2": {"type": "group", "items": "nope"},
        }},
    },
    {
        "name": "group with no repeat settings is an ordinary field",
        "form": {"fields": [_slide({"id": "g", "type": "group", "title": "Plain group", "properties": {"fields": []}})]},
        "response": {"response_id": "r10", "answers": {"g": {"type": "group", "items": []}}},
    },
    {
        "name": "group tabs never share a name",
        "form": {"fields": [_slide(
            _group(max_items=10, gid="g1", title="x" * 120),
            _group(max_items=10, gid="g2", title="x" * 120 + " (different tail)"),
            _group(max_items=10, gid="g3", title=("x" * 120).upper()),
            _group(max_items=10, gid="g4", title="Family: members/[all]"),
            _group(max_items=10, gid="g5", title="family  members  all"),
        )]},
        "response": {"response_id": "r11", "answers": {"g1": GROUP_ANSWER, "g2": GROUP_ANSWER}},
    },
    {
        "name": "group of calculated and sourced children",
        "form": {"fields": [_slide({
            "id": "g", "type": "group", "title": "Lines",
            "properties": {"repeat": {"max_items": 3, "item_label": "Line", "export_layout": "columns"}, "fields": [
                {"id": "qty", "type": "number", "title": "Qty"},
                {"id": "sum", "type": "calculated", "title": "Sum", "properties": {"format": {"style": "number", "decimals": 1}}},
                {"id": "who", "type": "dropdown", "title": "Who", "properties": {"option_source": {"kind": "list"}}},
            ]},
        })]},
        "response": {"response_id": "r12", "answers": {"g": {"type": "group", "items": [
            {"qty": {"number": 2}, "sum": {"number": 4.25}, "who": {"choice": {"value": "x", "label": "Alice"}}},
            {"qty": {"number": 3}},
        ]}}},
    },
    {
        "name": "form without fields",
        "form": {},
        "response": {},
    },
]
