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
