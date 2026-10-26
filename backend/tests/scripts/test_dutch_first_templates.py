"""The Dutch-first templates and their English twins: seeded with the flow
templates, one question per page, every question says why it asks, honest
defaults (few required answers, nothing pre-selected, follow-ups only after a
yes), and a form made from one keeps its language, publishes and accepts the
answers the template asks for."""

import datetime as dt
import json
import os
import re
from pathlib import Path

import pytest
from httpx import AsyncClient

from common.models.consent import ResponseRetentionType
from common.models.standard_form import WHY_WE_ASK_MAX_LENGTH, StandardForm

from backend.app.services.answer_validation import validate_answers, visited_slides
from backend.app.services.publish_checks import ID_NUMBER_TITLE, publish_problems
from backend.app.services.retention import MAX_RETENTION_DAYS, checked_retention
from scripts.dutch_first_templates import (
    BILINGUAL_BUILDERS,
    BILINGUAL_TEMPLATES,
    LANGUAGES,
    build_template,
)
from scripts.seed_flow_templates import (
    TEMPLATE_BUILDERS,
    seed_flow_templates,
    template_theme,
)

# What each template requires, and nothing more (the rest is optional).
REQUIRED = {
    "housing_application": {"name", "email", "household"},
    "school_enrolment": {"child_name", "child_birth_date", "parent_name", "email"},
    # email or phone, whichever the respondent chose (only that one is asked)
    "organisation_request": {"topic", "message", "name", "email", "phone"},
    "new_colleague": {"legal_name", "email", "birth_date", "address", "iban"},
    "event_registration": {"name", "email", "party_size"},
}
# Never in a template: no government body, no national identity number.
FORBIDDEN = re.compile(
    r"\b(gemeente|municipal\w*|overheid|government|ministerie|ministry|rijks\w*"
    r"|digid|bsn|burgerservicenummer)\b",
    re.IGNORECASE,
)
# B1 plain language: short sentences.
MAX_WORDS_PER_SENTENCE = 20

SAMPLE_ANSWERS = {
    "short_text": {"text": "Sam de Vries"},
    "long_text": {"text": "Geen bijzonderheden."},
    "email": {"email": "sam@example.org"},
    "phone_number": {"phone_number": "+31612345678"},
    "number": {"number": 2},
    "date": {"date": "2000-01-31"},
}


def _form(payload: dict) -> StandardForm:
    # As seeded: the template's theme comes with the form, so the publish
    # checks include theme_contrast.
    return StandardForm(
        theme=template_theme(),
        title=payload["title"],
        description=payload["description"],
        fields=payload["fields"],
        builder_version="v2",
        welcome_page=payload["welcome_page"],
        thankyou_page=payload["thankyou_page"],
        settings={"language": payload["language"]},
    )


def _questions(payload: dict) -> list:
    return [page["properties"]["fields"][0] for page in payload["fields"]]


def _texts(payload: dict) -> list:
    texts = [
        payload["title"],
        payload["description"],
        payload["welcome_page"]["description"],
        payload["welcome_page"]["buttonText"],
    ]
    for ending in payload["thankyou_page"]:
        texts += [ending["title"], ending["message"]]
    for question in _questions(payload):
        texts += [question["title"], question["properties"]["why_we_ask"]]
        texts += [c["value"] for c in question["properties"].get("choices", [])]
    return texts


def _shape(payload: dict) -> list:
    """The template without its words: what twins must share."""
    page_index = {page["id"]: i for i, page in enumerate(payload["fields"])}
    field_index = {question["id"]: i for i, question in enumerate(_questions(payload))}
    shape = []
    for page in payload["fields"]:
        question = page["properties"]["fields"][0]
        props = question["properties"]
        shape.append(
            (
                question["type"],
                question.get("validations"),
                len(props.get("choices", [])),
                props.get("date_rules"),
                [
                    (
                        field_index[jump["conditions"][0]["field_id"]],
                        jump["conditions"][0]["comparison"],
                        page_index.get(jump["target"], jump["target"]),
                    )
                    for jump in page["properties"].get("jumps", [])
                ],
            )
        )
    return shape


def test_every_template_is_seeded_in_dutch_and_english():
    names = [build.__name__ for build in TEMPLATE_BUILDERS]
    for template in BILINGUAL_TEMPLATES:
        for lang in LANGUAGES:
            assert f"{template.key}_{lang}" in names
    assert len(BILINGUAL_BUILDERS) == 2 * len(BILINGUAL_TEMPLATES) == 10
    for build in BILINGUAL_BUILDERS:
        assert build()["language"] == build.__name__.rsplit("_", 1)[1]
    # The seed matches templates by title: every title is its own.
    titles = [build()["title"] for build in TEMPLATE_BUILDERS]
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize("template", BILINGUAL_TEMPLATES, ids=lambda t: t.key)
def test_twins_ask_the_same_questions_in_their_own_language(template):
    dutch, english = build_template(template, "nl"), build_template(template, "en")
    assert _shape(dutch) == _shape(english)
    for nl, en in zip(_questions(dutch), _questions(english)):
        assert nl["title"] != en["title"]
        assert nl["properties"]["why_we_ask"] != en["properties"]["why_we_ask"]
    assert dutch["welcome_page"]["buttonText"] == "Beginnen"


@pytest.mark.parametrize("build", BILINGUAL_BUILDERS, ids=lambda b: b.__name__)
def test_one_question_per_page_and_each_says_why(build):
    payload = build()
    for page in payload["fields"]:
        assert page["type"] == "slide"
        assert len(page["properties"]["fields"]) == 1
    for question in _questions(payload):
        why = question["properties"]["why_we_ask"]
        assert why.strip() and len(why) <= WHY_WE_ASK_MAX_LENGTH
        assert "?" in question["title"], question["title"]
    assert payload["welcome_page"]["description"]
    assert all(e["title"] and e["message"] for e in payload["thankyou_page"])


@pytest.mark.parametrize("build", BILINGUAL_BUILDERS, ids=lambda b: b.__name__)
def test_honest_defaults(build):
    payload = build()
    template = next(t for t in BILINGUAL_TEMPLATES if build.__name__.startswith(t.key))
    by_key = dict(zip((q.key for q in template.questions), _questions(payload)))
    required = {
        key
        for key, question in by_key.items()
        if (question.get("validations") or {}).get("required")
    }
    assert required == REQUIRED[template.key]
    for question in by_key.values():
        # nothing chosen for the respondent, no documents, no ID numbers
        assert "value" not in question
        assert question["type"] not in ("file_upload", "calculated")
        assert not ID_NUMBER_TITLE.search(question["title"])
        if question["type"] == "yes_no":
            assert not (question.get("validations") or {}).get("required")
            assert [c["value"] for c in question["properties"]["choices"]] == [
                "Yes",
                "No",
            ]
    assert publish_problems(_form(payload)) == []


@pytest.mark.parametrize("build", BILINGUAL_BUILDERS, ids=lambda b: b.__name__)
def test_plain_language_and_no_government_wording(build):
    for text in _texts(build()):
        assert not FORBIDDEN.search(text), text
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            assert len(sentence.split()) <= MAX_WORDS_PER_SENTENCE, sentence


# The respondent page states the retention from the setting; a template must
# not also claim one in its own words (the two could disagree).
RETENTION_CLAIM = re.compile(
    r"\b(bewaar\w*|verwijder\w*|gewist|wissen|we\s+houden|retain\w*|retention"
    r"|delet\w+|erase\w*|we\s+keep\s+(it|your|this|them|the)|kept|stored?\s+for)\b"
    r"|\b\d+\s*(dagen|weken|maanden|jaar|days|weeks|months|years)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("build", BILINGUAL_BUILDERS, ids=lambda b: b.__name__)
def test_answers_are_deleted_after_a_set_period_not_promised_in_words(build):
    payload = build()
    template = next(t for t in BILINGUAL_TEMPLATES if build.__name__.startswith(t.key))
    assert payload["response_expiration_type"] == "days"
    days = int(payload["response_expiration"])
    assert 1 <= days <= MAX_RETENTION_DAYS
    assert days == template.retention_days
    # the form's own retention setting, as the server reads it
    form = _form(payload)
    assert checked_retention(
        payload["response_expiration_type"],
        payload["response_expiration"],
        dt.date.today(),
    ) == (ResponseRetentionType.DAYS, str(days))
    for text in _texts(payload):
        assert not RETENTION_CLAIM.search(text), text
    assert form.settings.language == payload["language"]


def test_twins_keep_answers_equally_long():
    for template in BILINGUAL_TEMPLATES:
        nl, en = (build_template(template, lang) for lang in LANGUAGES)
        assert nl["response_expiration"] == en["response_expiration"]


FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "webapp/src/utils/plain-language/dutch-first-templates.fixture.json"
)


def prose_of_templates() -> list:
    """Every sentence a respondent reads in the templates (not the choices or
    button labels), by language: what the webapp's plain-language (B1) check
    runs over (plain-language/dutch-first-templates.test.ts)."""
    rows = []
    for template in BILINGUAL_TEMPLATES:
        for lang in LANGUAGES:
            payload = build_template(template, lang)
            texts = [
                ("title", payload["title"]),
                ("description", payload["description"]),
                ("welcome", payload["welcome_page"]["description"]),
            ]
            for ending in payload["thankyou_page"]:
                texts += [("ending", ending["title"]), ("ending", ending["message"])]
            for question in _questions(payload):
                texts += [
                    ("question", question["title"]),
                    ("why", question["properties"]["why_we_ask"]),
                ]
            rows += [
                {"template": template.key, "language": lang, "kind": kind, "text": text}
                for kind, text in texts
            ]
    return rows


def test_the_webapp_plain_language_check_reads_the_current_wording():
    """The webapp's B1 check (a TypeScript test) runs over a copy of the
    templates' prose; this keeps the copy current. After changing a
    template's wording, regenerate it with REGENERATE_TEMPLATE_PROSE=1."""
    rows = prose_of_templates()
    if os.environ.get("REGENERATE_TEMPLATE_PROSE") == "1":
        lines = ",\n".join("  " + json.dumps(row, ensure_ascii=False) for row in rows)
        FIXTURE.write_text("[\n" + lines + "\n]\n")
    assert json.loads(FIXTURE.read_text()) == rows


def _answer(question: dict, yes: bool) -> dict:
    if question["type"] == "yes_no":
        return {"boolean": yes}
    if question["type"] == "multiple_choice":
        # a choice answer names the choice by its id
        return {"choice": {"value": question["properties"]["choices"][0]["id"]}}
    return SAMPLE_ANSWERS[question["type"]]


@pytest.mark.parametrize("build", BILINGUAL_BUILDERS, ids=lambda b: b.__name__)
def test_follow_ups_are_shown_only_after_a_yes(build):
    payload = build()
    form = _form(payload)
    questions = _questions(payload)
    required_only = {
        q["id"]: _answer(q, yes=False)
        for q in questions
        if (q.get("validations") or {}).get("required")
    }
    # The required answers alone are a complete response.
    assert validate_answers(form, required_only) == []
    every_yes = {q["id"]: _answer(q, yes=True) for q in questions}
    assert validate_answers(form, every_yes) == []

    skipped = {page.id for page in form.fields} - {
        page.id for page in visited_slides(form.fields, required_only)
    }
    shown_after_yes = {page.id for page in visited_slides(form.fields, every_yes)}
    # A page skipped without a yes is a follow-up a yes shows.
    assert skipped <= shown_after_yes
    assert bool(skipped) == any(
        page["properties"].get("jumps") for page in payload["fields"]
    )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_the_request_asks_only_for_the_chosen_contact_detail(lang):
    payload = build_template(
        next(t for t in BILINGUAL_TEMPLATES if t.key == "organisation_request"), lang
    )
    form = _form(payload)
    questions = _questions(payload)
    call_me = next(q for q in questions if q["type"] == "yes_no")
    email = next(q for q in questions if q["type"] == "email")
    phone = next(q for q in questions if q["type"] == "phone_number")
    base = {
        q["id"]: _answer(q, yes=False)
        for q in questions
        if (q.get("validations") or {}).get("required")
        and q["id"] not in (email["id"], phone["id"])
    }

    def asked(call: object) -> set:
        answers = dict(base)
        if call is not None:
            answers[call_me["id"]] = {"boolean": call}
        return {
            page.properties.fields[0].id
            for page in visited_slides(form.fields, answers)
        } & {email["id"], phone["id"]}

    assert asked(None) == {email["id"]}
    assert asked(False) == {email["id"]}
    assert asked(True) == {phone["id"]}


@pytest.mark.asyncio
async def test_a_seeded_dutch_template_becomes_a_dutch_form_that_publishes(
    client: AsyncClient, workspace, test_user_cookies
):
    from backend.app.container import container

    result = await seed_flow_templates(
        workspace.id, template_repo=container.form_template_repo()
    )
    for build in BILINGUAL_BUILDERS:
        assert build()["title"] in result["seeded"]

    listed = await client.get(
        "/api/v1/templates",
        params={"v2": True, "workspace_id": str(workspace.id)},
        cookies=test_user_cookies,
    )
    assert listed.status_code == 200
    by_title = {t["title"]: t for t in listed.json()}
    for template in BILINGUAL_TEMPLATES:
        for lang in LANGUAGES:
            listed_one = by_title[template.title[lang]]
            assert listed_one["settings"]["language"] == lang
            assert listed_one["welcomePage"]["description"] == template.welcome[lang]
    # newest first: each Dutch template is listed before its English twin
    order = [t["title"] for t in listed.json()]
    for template in BILINGUAL_TEMPLATES:
        assert order.index(template.title["nl"]) < order.index(template.title["en"])

    dutch = by_title["Aanmelding voor school"]
    listed_dutch_school = dutch
    created = await client.post(
        f"/api/v1/workspaces/{workspace.id}/template/{dutch['id']}",
        cookies=test_user_cookies,
    )
    assert created.status_code == 200, created.text
    form = created.json()
    assert form["settings"]["language"] == "nl"
    # the template's retention is the new form's enforced one
    assert listed_dutch_school["settings"]["responseExpirationType"] == "days"
    assert form["settings"]["responseExpirationType"] == "days"
    assert form["settings"]["responseExpiration"] == "365"
    assert form["welcomePage"]["buttonText"] == "Beginnen"
    assert [e["title"] for e in form["thankyouPage"]] == ["Bedankt voor uw aanmelding"]
    first = form["fields"][0]["properties"]["fields"][0]
    assert first["title"] == "Wat is de naam van uw kind?"
    assert first["properties"]["whyWeAsk"] == "Zo weten we wie u aanmeldt."

    published = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form['formId']}/publish",
        cookies=test_user_cookies,
    )
    assert published.status_code == 200, published.text

    again = await seed_flow_templates(
        workspace.id, template_repo=container.form_template_repo()
    )
    assert again["seeded"] == []
