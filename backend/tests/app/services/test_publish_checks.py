"""Honest defaults enforced at publish (services/publish_checks.py): a reason on
every identifying question, no required dead ends, no preset answers. The
retention a form states is applied to every submission (services/retention.py)."""

import datetime as dt

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    FieldLogic,
    FieldLogicCondition,
    RepeatSettings,
    StandardChoice,
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
)

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.dtos.settings_patch import SettingsPatchDto
from backend.app.services.ai.ops import FormOps, apply_form_ops
from backend.app.services.publish_checks import (
    MISSING_WHY_WE_ASK,
    PRESET_ANSWER,
    REQUIRED_UNANSWERABLE,
    asks_for_identity,
    ensure_publishable,
    publish_problems,
)
from backend.app.services.retention import submission_expiry
from tests.app.controllers.data import testUser, testUser2


def _q(id_, type_, title="Question", required=False, **props):
    return StandardFormField(
        id=id_,
        type=type_,
        title=title,
        properties=StandardFieldProperty(fields=[], **props),
        validations=StandardFieldValidations(required=required or None),
    )


def _form(*fields, extra_pages=()):
    return StandardForm(
        title="Form",
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(fields=list(fields)),
            ),
            *extra_pages,
        ],
    )


def _codes(form):
    return [(p["code"], p["fieldId"]) for p in publish_problems(form)]


# --- why we ask this ---------------------------------------------------------


@pytest.mark.parametrize("field_type", [T.EMAIL, T.PHONE_NUMBER])
def test_email_and_phone_need_a_reason(field_type):
    assert _codes(_form(_q("q", field_type, "Your contact"))) == [
        (MISSING_WHY_WE_ASK, "q")
    ]
    assert _codes(_form(_q("q", field_type, why_we_ask="   "))) == [
        (MISSING_WHY_WE_ASK, "q")
    ]
    assert _codes(_form(_q("q", field_type, why_we_ask="To reply to you."))) == []


@pytest.mark.parametrize(
    "title",
    [
        "Your BSN",
        "Burgerservicenummer",
        "Passport number",
        "Paspoortnummer",
        "ID number",
        "ID-nummer",
        "National insurance number",
        "Social security number",
    ],
)
def test_id_number_questions_are_recognised(title):
    assert asks_for_identity(_q("q", T.SHORT_TEXT, title))


@pytest.mark.parametrize(
    "title",
    ["Order ID", "Passport photo attached?", "Your idea", "Number of guests", "Bsnl"],
)
def test_the_id_heuristic_stays_narrow(title):
    assert not asks_for_identity(_q("q", T.SHORT_TEXT, title))


def test_id_number_titles_in_rich_text_are_read():
    field = _q("q", T.NUMBER)
    field.title = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Uw BSN"}]}],
    }
    assert asks_for_identity(field)


def test_internal_fields_are_not_respondent_facing():
    field = _q("q", T.EMAIL)
    field.internal = True
    assert _codes(_form(field)) == []


def test_questions_inside_a_repeating_group_are_checked():
    group = _q(
        "g",
        T.GROUP,
        "Applicants",
        repeat=RepeatSettings(max_items=3),
    )
    group.properties.fields = [_q("child", T.EMAIL, "Applicant email")]
    assert _codes(_form(group)) == [(MISSING_WHY_WE_ASK, "child")]


# --- required dead ends ------------------------------------------------------


@pytest.mark.parametrize("field_type", [T.TEXT, T.IMAGE_CONTENT, T.VIDEO_CONTENT])
def test_required_display_only_content_is_a_dead_end(field_type):
    assert _codes(_form(_q("q", field_type, required=True))) == [
        (REQUIRED_UNANSWERABLE, "q")
    ]
    assert _codes(_form(_q("q", field_type))) == []


def test_required_plain_group_is_a_dead_end():
    assert _codes(_form(_q("g", T.GROUP, required=True))) == [
        (REQUIRED_UNANSWERABLE, "g")
    ]


@pytest.mark.parametrize("field_type", [T.DROPDOWN, T.MULTIPLE_CHOICE])
def test_required_choice_without_options_is_a_dead_end(field_type):
    empty = _q("q", field_type, required=True, choices=[StandardChoice(id="c", value=" ")])
    assert _codes(_form(empty)) == [(REQUIRED_UNANSWERABLE, "q")]
    ok = _q("q", field_type, required=True, choices=[StandardChoice(id="c", value="A")])
    assert _codes(_form(ok)) == []


def test_required_grid_without_columns_is_a_dead_end():
    grid = _q("m", T.MATRIX, required=True)
    grid.properties.fields = [_q("row", T.MULTIPLE_CHOICE, "Row", choices=[])]
    assert _codes(_form(grid)) == [(REQUIRED_UNANSWERABLE, "m")]


def test_required_yes_no_without_stored_choices_is_answerable():
    # The respondent form falls back to Yes/No.
    assert _codes(_form(_q("q", T.YES_NO, required=True))) == []


def test_required_questions_hidden_by_logic_or_skipped_are_not_dead_ends():
    hidden = _q("q", T.SHORT_TEXT, "Details", required=True)
    hidden.properties.logic = FieldLogic(
        action="SHOW",
        operator="AND",
        conditions=[
            FieldLogicCondition(field_id="other", comparison="is_equal", value="x")
        ],
    )
    form = _form(_q("other", T.SHORT_TEXT, "Other"), hidden)
    assert _codes(form) == []


# --- preset answers ----------------------------------------------------------


def test_a_preset_answer_on_a_choice_question_blocks_publishing():
    consent = _q("c", T.YES_NO, "I agree to be contacted")
    consent.value = "Yes"
    assert _codes(_form(consent)) == [(PRESET_ANSWER, "c")]
    consent.value = ""
    assert _codes(_form(consent)) == []


def test_a_preset_option_on_a_choice_question_blocks_publishing():
    field = _q(
        "d",
        T.DROPDOWN,
        "Newsletter",
        choices=[StandardChoice(id="1", value="Subscribe"), StandardChoice(id="2", value="No thanks")],
    )
    field.value = "subscribe"
    assert _codes(_form(field)) == [(PRESET_ANSWER, "d")]


def test_a_legacy_title_in_value_is_not_a_preset_answer():
    # Fields from before rich-text titles keep their question in ``value``.
    consent = _q("c", T.YES_NO, None)
    consent.value = "Do you agree to be contacted?"
    text = _q("t", T.SHORT_TEXT, "Name")
    text.value = "Name"
    assert _codes(_form(consent, text)) == []


def test_ensure_publishable_lists_every_problem():
    form = _form(_q("e", T.EMAIL, "Email"), _q("s", T.TEXT, "Intro", required=True))
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(form)
    assert raised.value.status_code == 422
    content = raised.value.content
    assert content["code"] == "form_not_publishable"
    assert [p["fieldId"] for p in content["problems"]] == ["e", "s"]
    assert '"Email"' in content["message"]


# --- through the service and the API -----------------------------------------


async def _draft_with(workspace, *fields):
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(*fields), testUser
    )
    return form.form_id


async def test_publish_is_refused_until_the_reason_is_given(workspace):
    form_id = await _draft_with(workspace, _q("e", T.EMAIL, "Your email"))
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    assert raised.value.status_code == 422
    assert raised.value.content["problems"][0]["code"] == MISSING_WHY_WE_ASK

    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.fields[0].properties.fields[0].properties.why_we_ask = "To send a receipt."
    await container.form_service().update_form(form_id=form_id, form=draft)
    published = await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    assert published.fields[0].properties.fields[0].properties.why_we_ask == (
        "To send a receipt."
    )


async def test_publish_endpoint_answers_422_with_the_problems(
    client: AsyncClient, workspace, test_user_cookies
):
    form_id = await _draft_with(workspace, _q("p", T.PHONE_NUMBER, "Phone"))
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/publish",
        cookies=test_user_cookies,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "form_not_publishable"
    assert body["problems"] == [
        {
            "code": MISSING_WHY_WE_ASK,
            "fieldId": "p",
            "message": body["problems"][0]["message"],
        }
    ]


def test_ai_ops_set_and_clear_the_reason():
    add = {
        "op": "add_field",
        "pageId": "page-1",
        "field": {"title": "Email", "type": "email", "whyWeAsk": " To reply. "},
    }
    form, results = apply_form_ops(_form(), FormOps.model_validate({"ops": [add]}).ops)
    assert all(r.ok for r in results)
    field = form.fields[0].properties.fields[0]
    assert field.properties.why_we_ask == "To reply."
    clear = {"op": "update_field", "fieldId": field.id, "patch": {"whyWeAsk": ""}}
    form, results = apply_form_ops(form, FormOps.model_validate({"ops": [clear]}).ops)
    assert all(r.ok for r in results)
    assert form.fields[0].properties.fields[0].properties.why_we_ask is None


# --- retention ---------------------------------------------------------------

NOW = dt.datetime(2026, 10, 6, 12, 30, 15, 123456)


def test_days_retention_expires_that_many_days_later():
    expiry = submission_expiry(
        {"response_expiration_type": "days", "response_expiration": "90"}, NOW
    )
    assert expiry == ("2027-01-04T12:30:15.123Z", "days")


def test_date_retention_expires_on_that_day():
    expiry = submission_expiry(
        {"response_expiration_type": "date", "response_expiration": "2027-03-01"}, NOW
    )
    assert expiry == ("2027-03-01T00:00:00.000Z", "date")


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {"response_expiration_type": "forever"},
        {"response_expiration_type": "days", "response_expiration": "0"},
        {"response_expiration_type": "days", "response_expiration": "ninety"},
        {"response_expiration_type": "date", "response_expiration": "2027-02-30"},
    ],
)
def test_no_or_unreadable_retention_keeps_answers(settings):
    assert submission_expiry(settings, NOW) is None


@pytest.mark.parametrize(
    "body",
    [
        {"responseExpirationType": "days", "responseExpiration": "0"},
        {"responseExpirationType": "days", "responseExpiration": "99999"},
        {"responseExpirationType": "date", "responseExpiration": "2000-01-01"},
        {"responseExpirationType": "date", "responseExpiration": "soon"},
        {"responseExpiration": "30"},
    ],
)
def test_retention_settings_are_validated(body):
    with pytest.raises(ValueError):
        SettingsPatchDto(**body)


async def test_the_stated_retention_is_applied_to_submissions(
    workspace, published_form
):
    await container.form_service().patch_settings_in_workspace_form(
        workspace.id,
        published_form.form_id,
        SettingsPatchDto(response_expiration_type="days", response_expiration="30"),
        testUser,
    )
    before = dt.datetime.utcnow()
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        # Whatever the client claims, the form's retention applies.
        StandardFormResponseCamelModel(answers={}, expiration_type="forever"),
        testUser2,
    )
    stored = await container.form_response_repo().get_response(response.response_id)
    assert getattr(stored.expiration_type, "value", stored.expiration_type) == "days"
    expires = dt.datetime.strptime(stored.expiration, "%Y-%m-%dT%H:%M:%S.%fZ")
    assert dt.timedelta(days=29, hours=23) < expires - before < dt.timedelta(days=30, minutes=5)

    # "Until deleted" again: new submissions keep no expiry.
    await container.form_service().patch_settings_in_workspace_form(
        workspace.id,
        published_form.form_id,
        SettingsPatchDto(response_expiration_type="forever"),
        testUser,
    )
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}),
        testUser2,
    )
    stored = await container.form_response_repo().get_response(response.response_id)
    assert stored.expiration is None
