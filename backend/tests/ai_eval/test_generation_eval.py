"""AI form-generation eval harness v1 (plan §2.1 / P0.4).

Golden prompts with schema + rubric assertions, run against the LIVE
provider — so this suite is opt-in and NEVER part of the normal test run:

    GOOGLE_AI_API_KEY=... AI_EVAL=1 uv run pytest tests/ai_eval -q

Purpose: catch quality regressions when the prompt, provider, or model
changes (e.g. "choice fields stopped getting options", "purpose disappeared",
"invalid JSON"). Keep the golden set small — each case is a real model call.

The rubric asserts structure, not wording: the schema converts and validates,
choice fields have >=2 options, ratings have steps, expected field types
appear for unambiguous prompts, and nothing violates the no-dark-patterns
laws that are assertable (no pre-ticked consent).
"""

import asyncio
import os

import pytest
from common.models.standard_form import StandardForm, StandardFormFieldType

RUN_EVALS = bool(os.getenv("AI_EVAL")) and bool(os.getenv("GOOGLE_AI_API_KEY"))

pytestmark = pytest.mark.skipif(
    not RUN_EVALS,
    reason="AI evals are opt-in: set AI_EVAL=1 and GOOGLE_AI_API_KEY to run live provider calls.",
)

# (prompt, field types that MUST appear somewhere in the generated form)
GOLDEN_PROMPTS = [
    (
        "A customer feedback form for a small bakery: name, email, overall rating, and what we could do better.",
        {StandardFormFieldType.EMAIL, StandardFormFieldType.RATING},
    ),
    (
        "An RSVP form for a wedding: guest name, attending yes/no, dietary requirements, number of guests.",
        {StandardFormFieldType.YES_NO, StandardFormFieldType.NUMBER},
    ),
    (
        "A job application form: full name, email, phone, CV upload, and why do you want to work here.",
        {StandardFormFieldType.EMAIL, StandardFormFieldType.PHONE_NUMBER, StandardFormFieldType.FILE_UPLOAD},
    ),
    (
        "A newsletter signup with just an email address and a topic preference dropdown.",
        {StandardFormFieldType.EMAIL, StandardFormFieldType.DROPDOWN},
    ),
    (
        "An NPS survey: how likely are you to recommend us on a 0-10 scale, plus one open comment.",
        {StandardFormFieldType.LINEAR_RATING, StandardFormFieldType.LONG_TEXT},
    ),
    (
        "A doctor's appointment booking form collecting patient name, date of birth, preferred appointment date and reason for visit.",
        {StandardFormFieldType.DATE},
    ),
]


def _all_fields(form: StandardForm):
    for slide in form.fields or []:
        if slide.type == StandardFormFieldType.SLIDE:
            yield from (slide.properties.fields if slide.properties else None) or []


def _generate(prompt: str) -> StandardForm:
    from backend.app.container import container

    service = container.openai_service()
    provider = service._get_provider(None)  # default provider
    raw = asyncio.get_event_loop().run_until_complete(provider.generate_form(prompt))
    form = service.convert_openai_form_to_standard_form(openai_form=raw)
    # The schema is the first rubric line: it must round-trip validation.
    return StandardForm.model_validate(form.model_dump())


@pytest.mark.parametrize("prompt,expected_types", GOLDEN_PROMPTS, ids=[p[:40] for p, _ in GOLDEN_PROMPTS])
def test_golden_prompt(prompt, expected_types):
    form = _generate(prompt)

    # Structure sanity
    assert form.title and form.title.strip(), "form must have a title"
    slides = [f for f in form.fields or [] if f.type == StandardFormFieldType.SLIDE]
    assert slides, "form must have at least one page"
    fields = list(_all_fields(form))
    assert fields, "form must have at least one field"

    # Rubric: type coverage for unambiguous asks
    present = {f.type for f in fields}
    missing = expected_types - present
    assert not missing, f"expected field types missing: {sorted(t.value for t in missing)} (got {sorted(t.value for t in present if t)})"

    # Rubric: field-level invariants
    for field in fields:
        if field.type in (StandardFormFieldType.MULTIPLE_CHOICE, StandardFormFieldType.DROPDOWN):
            choices = (field.properties.choices if field.properties else None) or []
            assert len(choices) >= 2, f"choice field '{field.title}' has {len(choices)} options"
        if field.type in (StandardFormFieldType.RATING, StandardFormFieldType.LINEAR_RATING):
            assert field.properties and field.properties.steps, f"rating field '{field.title}' has no steps"

    # No-dark-patterns (assertable subset): consent, if generated, is opt-in.
    for consent in form.consent or []:
        checked = getattr(consent, "checked", None)
        assert not checked, "consent must never be pre-ticked"
