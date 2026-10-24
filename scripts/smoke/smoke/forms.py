"""The forms the suite works with (pure: specs, expected answers, comparison).

* The standing set: one form with several field types and a few responses,
  created on the first run and kept. Every later run reads those responses
  back and compares them with the values below: the canary for the keys and
  the response codec across releases (a response that no longer decrypts
  reads as empty answers, which fails the comparison).
* The run form: created, published, answered and deleted by each run.

All values are made up; none is personal data.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

STANDING_TITLE = "Smoke test standing set (keep, do not edit)"
PURPOSE = "Automated smoke test of this instance. Test data only."

# field id -> (type, title, choices)
STANDING_FIELDS = [
    ("name", "short_text", "Name", None),
    ("about", "long_text", "About", None),
    ("mail", "email", "Email", None),
    ("count", "number", "Count", None),
    ("colour", "multiple_choice", "Colour", ["Blue", "Green"]),
    ("agree", "yes_no", "Agree", ["Yes", "No"]),
]

STANDING_RESPONSES: List[Dict[str, str]] = [
    {
        "name": "Standing one",
        "about": "The first standing response.",
        "mail": "standing-one@example.com",
        "count": "1",
        "colour": "Blue",
        "agree": "Yes",
    },
    {
        "name": "Standing two",
        "about": "The second standing response.",
        "mail": "standing-two@example.com",
        "count": "2",
        "colour": "Green",
        "agree": "No",
    },
    {
        "name": "Standing three",
        "about": "The third standing response.",
        "mail": "standing-three@example.com",
        "count": "3",
        "colour": "Blue",
        "agree": "No",
    },
]


def choice_id(field_id: str, label: str) -> str:
    return f"{field_id}-{label.lower()}"


def stored_value(field_id: str, given: str) -> str:
    """What a stored answer holds for the value typed or picked: a multiple
    choice keeps the choice's id."""
    kinds = {f[0]: f[1] for f in STANDING_FIELDS}
    if kinds.get(field_id) == "multiple_choice":
        return choice_id(field_id, given)
    return given


def _field(field_id: str, kind: str, title: str, choices: Optional[List[str]]) -> dict:
    field: Dict[str, Any] = {
        "id": field_id,
        "type": kind,
        "title": title,
        "validations": {"required": True},
    }
    if choices:
        # explicit ids: the respondent page answers a choice by its id
        field["choices"] = [{"id": choice_id(field_id, c), "value": c} for c in choices]
    if kind in PERSONAL_TYPES:
        # publishing asks why a personal detail is collected
        field["whyWeAsk"] = "Test data only: checks that answers are kept."
    return field


def standing_spec() -> dict:
    return {
        "specVersion": "1",
        "title": STANDING_TITLE,
        "language": "en",
        "pages": [
            {
                "id": "page-1",
                "fields": [_field(*f) for f in STANDING_FIELDS],
            }
        ],
        "endings": [{"title": "Thanks", "message": "Recorded."}],
        "trust": {"purpose": PURPOSE},
    }


RUN_FIELD = "word"
PERSONAL_TYPES = {"email", "phone_number"}


def run_title(tag: str) -> str:
    return f"Smoke run {tag}"


def run_spec(tag: str) -> dict:
    return {
        "specVersion": "1",
        "title": run_title(tag),
        "language": "en",
        "pages": [
            {
                "id": "page-1",
                "fields": [_field(RUN_FIELD, "short_text", "Word", None)],
            }
        ],
        "endings": [{"title": "Thanks", "message": "Recorded."}],
        "trust": {"purpose": PURPOSE},
    }


def answer_value(answer: Any) -> Optional[str]:
    """The comparable value of one stored answer, whatever its type."""
    if not isinstance(answer, Mapping):
        return None
    for key in ("text", "email", "phone_number", "phoneNumber", "url", "date"):
        value = answer.get(key)
        if isinstance(value, str) and value != "":
            return value
    number = answer.get("number")
    if isinstance(number, str) and number.strip():
        try:
            number = float(number)
        except ValueError:
            return number.strip()
    if isinstance(number, (int, float)) and not isinstance(number, bool):
        return str(int(number)) if float(number).is_integer() else str(number)
    boolean = answer.get("boolean")
    if isinstance(boolean, bool):
        return "Yes" if boolean else "No"
    choice = answer.get("choice")
    if isinstance(choice, Mapping) and isinstance(choice.get("value"), str):
        return choice["value"]
    choices = answer.get("choices")
    if isinstance(choices, Mapping) and isinstance(choices.get("values"), list):
        return ", ".join(str(v) for v in choices["values"])
    return None


def answers_by_field(answers: Any) -> Dict[str, Optional[str]]:
    if not isinstance(answers, Mapping):
        return {}
    return {str(k): answer_value(v) for k, v in answers.items()}


def compare_standing(responses: List[Mapping[str, Any]]) -> List[str]:
    """Problems found comparing the stored responses (their ``answers``) with
    the standing set; an empty list means every expected response is there
    and reads back exactly. Problems name fields and positions, never values."""
    problems: List[str] = []
    found: Dict[str, Dict[str, Optional[str]]] = {}
    for position, response in enumerate(responses, 1):
        values = answers_by_field(response.get("answers"))
        if not values:
            problems.append(f"response {position} has no readable answers")
            continue
        name = values.get("name")
        if name in found:
            problems.append(f"response {position} repeats a standing response")
        if name:
            found[name] = values
    for index, expected in enumerate(STANDING_RESPONSES, 1):
        values = found.get(expected["name"])
        if values is None:
            problems.append(f"standing response {index} is missing")
            continue
        wrong = [f for f, v in expected.items() if values.get(f) != stored_value(f, v)]
        if wrong:
            problems.append(
                f"standing response {index} differs in: {', '.join(sorted(wrong))}"
            )
    return problems
