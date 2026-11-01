"""Answers both submission paths must judge the same way.

The respondent route and the public API's submissions endpoint run each case
against the same form (``SPEC``): the same status and the same problems
(question and rule code) must come out, and what is stored must be equal. The
answers are the typed answer objects both accept (the shape a response read
returns); the API's shorthand is tested on its own.
"""

SPEC = {
    "specVersion": "1",
    "title": "Event registration",
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {
                    "id": "name",
                    "type": "short_text",
                    "title": "Your name",
                    "validations": {"required": True, "maxLength": 20},
                },
                {
                    "id": "email",
                    "type": "email",
                    "title": "Your email",
                    "whyWeAsk": "To send the programme.",
                },
                {
                    "id": "age",
                    "type": "number",
                    "title": "Your age",
                    "validations": {"minValue": 18, "maxValue": 120},
                },
                {
                    "id": "dinner",
                    "type": "yes_no",
                    "title": "Will you join the dinner?",
                    "choices": [{"value": "Yes"}, {"value": "No"}],
                },
                {
                    "id": "meal",
                    "type": "dropdown",
                    "title": "Meal",
                    "choices": [
                        {"id": "veg", "value": "Vegetarian"},
                        {"id": "fish", "value": "Fish"},
                    ],
                    "logic": {
                        "action": "SHOW",
                        "operator": "AND",
                        "conditions": [
                            {
                                "fieldId": "dinner",
                                "fieldType": "yes_no",
                                "comparison": "IS_EQUAL",
                                "value": True,
                            }
                        ],
                    },
                },
            ],
        }
    ],
    "endings": [{"title": "Thanks", "message": "See you there."}],
    "trust": {"purpose": "To plan seats and catering."},
}


def text(value):
    return {"type": "text", "text": value}


def choice(option_id):
    return {"type": "choice", "choice": {"value": option_id}}


# (case id, answers, expected status, expected {(question, rule)})
CASES = [
    ("minimal valid answers", {"name": text("Ada")}, 201, set()),
    (
        "every question answered",
        {
            "name": text("Ada"),
            "email": {"type": "email", "email": "ada@example.org"},
            "age": {"type": "number", "number": 36},
            "dinner": {"type": "boolean", "boolean": True},
            "meal": choice("fish"),
        },
        201,
        set(),
    ),
    ("required question missing", {}, 422, {("name", "required")}),
    ("required question empty", {"name": text("")}, 422, {("name", "required")}),
    ("answer too long", {"name": text("x" * 21)}, 422, {("name", "too_long")}),
    (
        "number below the minimum",
        {"name": text("Ada"), "age": {"type": "number", "number": 3}},
        422,
        {("age", "too_small")},
    ),
    (
        "number above the maximum",
        {"name": text("Ada"), "age": {"type": "number", "number": 500}},
        422,
        {("age", "too_large")},
    ),
    (
        "wrong answer type",
        {"name": {"type": "number", "number": 3}},
        422,
        {("name", "type")},
    ),
    (
        "unknown question",
        {"name": text("Ada"), "nope": text("x")},
        422,
        {("nope", "unknown_field")},
    ),
    (
        "option the question does not have",
        {"name": text("Ada"), "dinner": {"type": "boolean", "boolean": True}, "meal": choice("steak")},
        422,
        {("meal", "choice")},
    ),
    (
        "several problems are all reported",
        {"age": {"type": "number", "number": 3}, "meal": choice("steak")},
        422,
        {("name", "required"), ("age", "too_small"), ("meal", "choice")},
    ),
]


# -- a richer form: pattern, calculated field, field rule, logic, the newer types, a repeating group ----

RICH_SPEC = {
    "specVersion": "1",
    "title": "Booking",
    "pages": [
        {
            "id": "page-1",
            "fields": [
                {
                    "id": "name",
                    "type": "short_text",
                    "title": "Your name",
                    "validations": {"required": True, "maxLength": 20},
                },
                {
                    "id": "code",
                    "type": "short_text",
                    "title": "Booking code",
                    "validations": {"pattern": "^[A-Z]{3}$"},
                },
                {"id": "qty", "type": "number", "title": "Tickets"},
                {"id": "extra", "type": "number", "title": "Extras"},
                {
                    "id": "total",
                    "type": "calculated",
                    "title": "Total",
                    "expression": {"+": [{"var": "qty"}, {"var": "extra"}]},
                },
                {
                    "id": "note",
                    "type": "short_text",
                    "title": "Note for large groups",
                    "rules": [
                        {
                            "id": "r1",
                            "when": {"expression": {">": [{"var": "qty"}, 10]}},
                            "then": {"required": True},
                        }
                    ],
                },
                {"id": "dinner", "type": "yes_no", "title": "Dinner?"},
                {
                    "id": "reason",
                    "type": "short_text",
                    "title": "Why dinner?",
                    "validations": {"required": True},
                    "logic": {
                        "action": "SHOW",
                        "operator": "AND",
                        "conditions": [
                            {
                                "fieldId": "dinner",
                                "fieldType": "yes_no",
                                "comparison": "IS_EQUAL",
                                "value": "Yes",
                            }
                        ],
                    },
                },
                {"id": "labels", "type": "tags", "title": "Labels"},
                {
                    "id": "price",
                    "type": "currency",
                    "title": "Price",
                    "currencies": ["EUR"],
                },
                {"id": "stay", "type": "date_range", "title": "Stay"},
                {
                    "id": "guests",
                    "type": "group",
                    "title": "Guests",
                    "repeat": {"minItems": 0, "maxItems": 3, "itemLabel": "Guest"},
                    "fields": [
                        {
                            "id": "gname",
                            "type": "short_text",
                            "title": "Guest name",
                            "validations": {"required": True},
                        },
                        {"id": "gage", "type": "number", "title": "Guest age"},
                    ],
                },
            ],
        }
    ],
    "endings": [{"title": "Thanks", "message": "See you there."}],
    "trust": {"purpose": "To plan the booking."},
}


def number(value):
    return {"type": "number", "number": value}


def guests(*items):
    return {"type": "group", "items": list(items)}


GUEST = {"gname": text("Bo"), "gage": number(30)}

# (case id, answers, expected status, expected {(question, rule)} or None: a 422 without per-question problems)
RICH_CASES = [
    ("pattern met", {"name": text("Ada"), "code": text("ABC")}, 201, set()),
    (
        "pattern broken",
        {"name": text("Ada"), "code": text("abc")},
        422,
        {("code", "pattern")},
    ),
    (
        "a calculated value sent by the caller is the server's to set",
        {
            "name": text("Ada"),
            "qty": number(3),
            "extra": number(4),
            "total": number(999),
        },
        201,
        set(),
    ),
    (
        "a field rule requires a question",
        {"name": text("Ada"), "qty": number(11)},
        422,
        {("note", "required")},
    ),
    (
        "a field rule met",
        {"name": text("Ada"), "qty": number(11), "note": text("bus")},
        201,
        set(),
    ),
    ("a field rule that does not apply", {"name": text("Ada"), "qty": number(5)}, 201, set()),
    (
        "a question hidden by logic is not required",
        {"name": text("Ada"), "dinner": {"type": "boolean", "boolean": False}},
        201,
        set(),
    ),
    (
        "a question shown by logic is required",
        {"name": text("Ada"), "dinner": {"type": "boolean", "boolean": True}},
        422,
        {("reason", "required")},
    ),
    (
        "tags",
        {"name": text("Ada"), "labels": {"type": "tags", "tags": ["vip", "late"]}},
        201,
        set(),
    ),
    (
        "tags repeating one",
        {"name": text("Ada"), "labels": {"type": "tags", "tags": ["vip", "VIP"]}},
        422,
        {("labels", "duplicate")},
    ),
    (
        "a currency",
        {
            "name": text("Ada"),
            "price": {"type": "currency", "currency": {"code": "EUR", "amount": "12.50"}},
        },
        201,
        set(),
    ),
    (
        "a currency the question does not offer",
        {
            "name": text("Ada"),
            "price": {"type": "currency", "currency": {"code": "USD", "amount": "12.50"}},
        },
        422,
        {("price", "currency")},
    ),
    (
        "a date range",
        {
            "name": text("Ada"),
            "stay": {"type": "date_range", "date_range": {"start": "2026-05-01", "end": "2026-05-04"}},
        },
        201,
        set(),
    ),
    (
        "a date range that ends before it starts",
        {
            "name": text("Ada"),
            "stay": {"type": "date_range", "date_range": {"start": "2026-05-04", "end": "2026-05-01"}},
        },
        422,
        {("stay", "range_order")},
    ),
    ("a repeating group", {"name": text("Ada"), "guests": guests(GUEST, GUEST)}, 201, set()),
    (
        "an item of a repeating group missing its required question",
        {"name": text("Ada"), "guests": guests({"gage": number(30)})},
        422,
        # (a group's structure and per-item Required are refused with a text,
        # not per question, by the respondent route; the API passes it on)
        None,
    ),
]
