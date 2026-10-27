"""Shared pieces of the Open Formulieren import tests."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from backend.config import settings

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "open_formulieren"
ENTRIES = (
    "forms.json",
    "formSteps.json",
    "formDefinitions.json",
    "formLogic.json",
    "formVariables.json",
    "_meta.json",
)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def load(name: str) -> Dict[str, Any]:
    """The decoded entries of a fixture archive, by entry name."""
    with zipfile.ZipFile(io.BytesIO(fixture_bytes(name))) as archive:
        return {entry: json.loads(archive.read(entry)) for entry in archive.namelist()}


def make_zip(
    entries: Dict[str, Any], *, deflate: bool = True, extra: Optional[dict] = None
) -> bytes:
    """An archive of ``entries`` (JSON values or raw bytes), the way their
    export writes it; ``extra`` adds raw entries."""
    buffer = io.BytesIO()
    kind = zipfile.ZIP_DEFLATED if deflate else zipfile.ZIP_STORED
    with zipfile.ZipFile(buffer, "w", kind) as archive:
        for name, value in {**entries, **(extra or {})}.items():
            data = value if isinstance(value, bytes) else json.dumps(value).encode()
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.fixture()
def import_on(monkeypatch):
    """OPEN_FORMULIEREN_IMPORT=on for the test."""
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")


GOLDEN = FIXTURES / "golden"
FIXTURE_NAMES = (
    "all-components.en.zip",
    "all-components.nl.zip",
    "logic-variables.en.zip",
    "signin-prefill-payment.en.zip",
    "special-components.en.zip",
    "appointment.en.zip",
)


def _value(value):
    return getattr(value, "value", value)


def describe(built) -> Dict[str, Any]:
    """A built draft as plain data for comparison: pages, questions (type,
    title, help, required, choices, answer rules, width, date rules, the
    visibility rule with its source named by title) and the report."""
    form = built.form
    titles: Dict[str, str] = {}
    for page in form.fields or []:
        for question in page.properties.fields or []:
            titles[question.id] = question.title
            for child in question.properties.fields or []:
                titles[child.id] = child.title

    def question(field) -> Dict[str, Any]:
        properties = field.properties
        entry: Dict[str, Any] = {"type": _value(field.type), "title": field.title}
        if properties.description:
            entry["description"] = properties.description
        if properties.placeholder:
            entry["placeholder"] = properties.placeholder
        rules = {
            k: v
            for k, v in (field.validations.model_dump() if field.validations else {}).items()
            if v is not None
        }
        if rules:
            entry["validations"] = rules
        if properties.choices and _value(field.type) not in ("yes_no",):
            entry["choices"] = [c.value for c in properties.choices]
        if properties.allow_multiple_selection:
            entry["allowMultiple"] = True
        if properties.col_span:
            entry["colSpan"] = properties.col_span
        if properties.date_rules:
            entry["dateRules"] = [
                r.model_dump(exclude_none=True, by_alias=True) for r in properties.date_rules
            ]
        if properties.logic:
            entry["logic"] = {
                "action": properties.logic.action,
                "operator": properties.logic.operator,
                "conditions": [
                    {
                        "source": titles[c.field_id],
                        "comparison": c.comparison,
                        **({"value": c.value} if c.value is not None else {}),
                    }
                    for c in properties.logic.conditions
                ],
            }
        if properties.repeat:
            entry["repeat"] = properties.repeat.model_dump(
                exclude_none=True, by_alias=True
            )
            entry["children"] = [question(c) for c in properties.fields or []]
        return entry

    pages = [
        {
            "title": page.properties.section_title,
            "questions": [question(q) for q in page.properties.fields or []],
        }
        for page in form.fields or []
    ]
    return {
        "title": form.title,
        "retention": [
            _value(form.settings.response_expiration_type),
            form.settings.response_expiration,
        ],
        "pages": pages,
        "summary": built.summary,
        "report": [
            {k: v for k, v in item.items() if k != "label"} for item in built.report.items
        ],
    }


def archive_with(
    steps,
    *,
    logic=None,
    form=None,
    variables=None,
    version="4.0.6",
    extra=None,
) -> bytes:
    """A synthetic export: ``steps`` is a list of component lists (one per
    step)."""
    definitions, step_entries = [], []
    for number, components in enumerate(steps):
        uuid = f"00000000-0000-4000-8000-{number:012d}"
        definitions.append(
            {
                "uuid": uuid,
                "name": f"Step {number + 1}",
                "slug": f"step-{number + 1}",
                "configuration": {"display": "form", "components": components},
            }
        )
        step_entries.append(
            {
                "uuid": f"10000000-0000-4000-8000-{number:012d}",
                "index": number,
                "slug": f"step-{number + 1}",
                "name": f"Step {number + 1}",
                "form_definition": f"http://localhost/api/v2/form-definitions/{uuid}",
            }
        )
    return make_zip(
        {
            "forms.json": [{"name": "Synthetic", "slug": "synthetic", **(form or {})}],
            "formSteps.json": step_entries,
            "formDefinitions.json": definitions,
            "formLogic.json": logic or [],
            "formVariables.json": variables or [],
            "_meta.json": {"of_release": version, "of_git_sha": "x", "created": "x"},
        },
        extra=extra,
    )


def comp(type_, key, label=None, **extra):
    return {"type": type_, "key": key, "label": label if label is not None else key, **extra}


def rule(trigger, *actions, order=0, description="rule"):
    return {
        "order": order,
        "description": description,
        "json_logic_trigger": trigger,
        "actions": list(actions),
        "is_advanced": False,
    }


def hide(component, state=True):
    return {
        "component": component,
        "action": {
            "type": "property",
            "property": {"value": "hidden", "type": "bool"},
            "state": state,
        },
    }


def eq(key, value):
    return {"==": [{"var": key}, value]}


# ------------------------------------------------------------------ timing
# Wall-clock assertions are fragile on a shared runner. Correctness tests never
# depend on the clock (the work budget's deadline is switched off for them);
# timing tests only (a) compare how the cost grows with the input, which
# separates linear from quadratic whatever the machine, or (b) allow a
# catastrophic bound far above any runner's speed.

import time

# generous: only a hang or a quadratic blow-up on hostile input gets near it
CATASTROPHIC_SECONDS = 30.0


def best_time(fn, runs: int = 3) -> float:
    """The fastest of ``runs`` calls of ``fn`` (seconds)."""
    best = float("inf")
    for _ in range(runs):
        started = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - started)
    return best


def assert_scales_linearly(make, small: int, large: int, factor: float = 3.0, floor: float = 0.05) -> None:
    """``make(n)`` returns a callable; its time for ``large`` may be at most
    ``factor`` times that for ``small`` (the sizes differ by 2x: linear is 2x,
    quadratic 4x), or both stay under ``floor`` seconds."""
    t_small = best_time(make(small))
    t_large = best_time(make(large))
    assert t_large <= max(factor * t_small, floor), (small, t_small, large, t_large)


@pytest.fixture()
def no_deadline(monkeypatch):
    """The build's wall-clock deadline switched off (and its text budget
    left as it is): for tests of what a big form imports to, not of speed."""
    from backend.app.services.open_formulieren import limits

    monkeypatch.setattr(limits, "BUILD_SECONDS", 1e9)
