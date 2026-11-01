"""Responses made through the public API (``POST`` and ``PATCH``
``/forms/{id}/submissions``).

There is no second implementation of any server rule here. A create builds
the respondent's own request object and calls the same
``WorkspaceFormService.submit_response`` the respondent route calls, with no
signed-in user (as an anonymous respondent arrives): the published version
only, open and close dates, the response limit, the answer checks (types,
Required, patterns, field rules, choice logic, calculated fields, date rules),
the retention the form states, encryption with the response keyset, and then
actions, webhooks, email actions and registration all run exactly as they do
for a respondent. An update calls ``patch_response_as_key``, which runs the
respondent edit's checks (``_apply_edit``).

What this module adds is in front of that call, and only refuses: the form
belongs to the key's workspace and to the key's form list, the form does not
ask for a verified respondent, the caller asserts the consent step, answers
are read into typed answer objects (``answers.py``) and the ones the API does
not take are refused. The key is recorded as the response's source, set here
and nowhere a request can reach.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional

from bson.errors import InvalidId
from common.ids import RecordId
from common.models.consent import ConsentType, ConsentResponse
from common.models.standard_form import SubmissionSource
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.constants.consents import default_consents
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.answer_validation import (
    ERROR_CODE,
    ERROR_MESSAGE,
    is_repeating_group,
)
from backend.app.services.submissions_api.answers import MAX_ANSWERS, build_answers

IDENTITY_REQUIRED = "respondent_identity_required"
CONSENT_REQUIRED = "consent_required"
FORM_NOT_ALLOWED = "form_not_allowed"
# a few characters and counts: the respondent's own limits are the draft's
MAX_HIDDEN_FIELDS = 50
MAX_HIDDEN_NAME = 200
MAX_HIDDEN_VALUE = 2000


class _Body(BaseModel):
    # unknown members are refused: the body can't carry an owner, a source, an
    # ending, a retention or anything else the server decides
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )


class CreateSubmission(_Body):
    answers: Dict[str, Any] = Field(
        description="By question id. Each value is the stored typed answer "
        "object (what a response read returns) or a shorthand for the "
        "common question types; null leaves a question unanswered.",
        max_length=MAX_ANSWERS,
    )
    hidden_fields: Optional[Dict[str, str]] = Field(
        None,
        description="Values for the form's declared hidden fields (what a "
        "share link's query string would carry), by name; names the form "
        "does not declare are left out.",
    )
    consent: Optional[bool] = Field(
        None,
        description="true: you assert that the respondent has given the "
        "consent the form asks for. Required when the form has a consent "
        "step; it is recorded as asserted by this API key.",
    )


class UpdateSubmission(_Body):
    answers: Dict[str, Any] = Field(
        description="By question id: the questions sent replace their stored "
        "answers, the others stay. Same value shapes as when creating.",
        max_length=MAX_ANSWERS,
    )


def _c():
    from backend.app.container import container

    return container


def _invalid(code: str, message: str, status: int = HTTPStatus.UNPROCESSABLE_ENTITY):
    return HTTPException(
        status_code=status, content={"code": code, "message": message}
    )


def parse_body(model: type, raw: Any):
    """The request body as ``model``, 422 ``invalid_request`` with the
    problem's JSON pointer when it does not fit."""
    if not isinstance(raw, dict):
        raise _invalid("invalid_request", "The body must be a JSON object.")
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        from common.form_spec import validation_errors

        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": "invalid_request",
                "message": "The request is not valid.",
                "errors": validation_errors(error),
            },
        )


def ensure_form_allowed(key: WorkspaceAPIKeyDocument, form_id: str) -> None:
    """403 when the key is limited to a list of forms and this is not one."""
    allowed = key.submission_form_ids
    if allowed is not None and str(form_id) not in allowed:
        raise _invalid(
            FORM_NOT_ALLOWED,
            "This API key may not submit to this form.",
            HTTPStatus.FORBIDDEN,
        )


async def _workspace_form(workspace_id: RecordId, form_id: str):
    association = await _c().workspace_form_repo().find_workspace_form(
        workspace_id, form_id
    )
    if association is None:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")
    return association


async def _published(form_id: str):
    form = await _c().form_service().get_latest_version_of_form(RecordId(form_id))
    if form is None:
        # never published: no version to answer, as for a respondent
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Form not found")
    return form


def _consent_items(form: Any) -> list:
    """The form's consent step: its own items, or the defaults the form page
    shows when it has none stored (``FormService`` serves them the same way)."""
    items = getattr(form, "consent", None)
    return list(default_consents if items is None else items)


def _consent_given(
    form: Any, asserted: Optional[bool]
) -> Optional[List[Dict[str, Any]]]:
    """The stored consent of the response: what a respondent who ticked the
    boxes would send, built by the server from the form's own items. 422
    ``consent_required`` when the form has a consent step and the caller did
    not assert it."""
    items = _consent_items(form)
    if not items:
        return None
    if asserted is not True:
        raise _invalid(
            CONSENT_REQUIRED,
            "This form asks for the respondent's consent. Send "
            '"consent": true to assert that it has been given.',
        )
    return [
        ConsentResponse(
            **item.model_dump(),
            accepted=True if item.type == ConsentType.CHECKBOX else None,
        ).model_dump()
        for item in items
    ]


def _hidden_values(form: Any, values: Optional[Dict[str, str]]) -> Dict[str, str]:
    declared = {str(n) for n in (getattr(form, "hidden_fields", None) or [])}
    kept = {k: v for k, v in (values or {}).items() if k in declared}
    if len(kept) > MAX_HIDDEN_FIELDS or any(
        len(k) > MAX_HIDDEN_NAME or len(v) > MAX_HIDDEN_VALUE for k, v in kept.items()
    ):
        raise _invalid("invalid_request", "Too many or too long hidden-field values.")
    return kept


# what each rule code of the answer check says, for the API's message
RULE_TEXT = {
    "required": "this question needs an answer",
    "too_short": "the answer is too short",
    "too_long": "the answer is too long",
    "pattern": "the answer does not match the format the form asks for",
    "too_small": "the number is below the minimum",
    "too_large": "the number is above the maximum",
    "not_integer": "a whole number is needed",
    "too_few_choices": "too few options are chosen",
    "too_many_choices": "too many options are chosen",
    "format": "the answer is not in the right format",
    "currency": "this currency is not accepted",
    "range_order": "the end comes before the start",
    "duplicate": "the answer repeats a value",
    "type": "the answer does not fit the question's type",
    "choice": "the answer is not one of the options",
    "unknown_field": "the form has no question with this id",
    "question_not_supported": "this kind of question can't be answered through the API",
}


def _located(form: Any, problem: Dict[str, Any]) -> Dict[str, str]:
    """One problem of the answer check as the API's ``{path, message}``: the
    path is a JSON pointer into the request body, the message starts with the
    rule's code."""
    field_id = str(problem.get("fieldId"))
    rule = str(problem.get("rule"))
    path = f"/answers/{field_id}"
    item = problem.get("item")
    if item is not None:
        for page in getattr(form, "fields", None) or []:
            for field in getattr(getattr(page, "properties", None), "fields", None) or []:
                if is_repeating_group(field) and any(
                    str(getattr(child, "id", "")) == field_id
                    for child in getattr(getattr(field, "properties", None), "fields", None)
                    or []
                ):
                    path = f"/answers/{field.id}/items/{item}/{field_id}"
    return {"path": path, "message": f"{rule}: {RULE_TEXT.get(rule, rule)}"}


def _refuse_problems(form: Any, problems: List[Dict[str, Any]]) -> None:
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": ERROR_MESSAGE,
                "errors": [_located(form, p) for p in problems],
            },
        )


def _api_errors(form: Any, error: HTTPException) -> HTTPException:
    """The respondent path's refusal of the answers, with the API's error
    shape: per question, located in the request body."""
    content = error.content
    if (
        isinstance(content, dict)
        and content.get("code") == ERROR_CODE
        and isinstance(content.get("errors"), list)
        and all(isinstance(e, dict) and "fieldId" in e for e in content["errors"])
    ):
        return HTTPException(
            status_code=error.status_code,
            content={
                **content,
                "errors": [_located(form, e) for e in content["errors"]],
            },
            headers=error.headers,
        )
    return error


async def create_submission(
    key: WorkspaceAPIKeyDocument, form_id: str, body: CreateSubmission
) -> Dict[str, Any]:
    from backend.config import settings

    # the respondent route's own gate on this feature
    if not settings.api_settings.ENABLE_FORM_CREATION:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")
    workspace_id = key.workspace_id
    association = await _workspace_form(workspace_id, form_id)
    ensure_form_allowed(key, form_id)
    form_settings = association.settings
    # A form that asks for a verified respondent, or is limited to admitted
    # responders, has someone to be: an API key is nobody (no identity, no
    # receipt, no OTP), so those forms refuse it.
    if form_settings and (
        form_settings.require_verified_identity or form_settings.private
    ):
        raise _invalid(
            IDENTITY_REQUIRED,
            "This form needs a signed-in respondent, so it does not take "
            "submissions from an API key.",
        )
    published = await _published(form_id)
    consent = _consent_given(published, body.consent)
    answers, problems = build_answers(published, body.answers)
    _refuse_problems(published, problems)
    request = StandardFormResponseCamelModel(
        answers=answers,
        hidden_fields=_hidden_values(published, body.hidden_fields) or None,
        consent=consent,
        # the version the answers are checked against, as the respondent's
        # page sends it: staff open the response in the form it was given in
        form_version=getattr(published, "version", None),
    )
    try:
        stored = await _c().workspace_form_service().submit_response(
            workspace_id=workspace_id,
            form_id=RecordId(form_id),
            response=request,
            user=None,
            source=SubmissionSource(
                channel="api",
                key_id=str(key.id),
                key_name=key.name,
                consent_asserted=consent is not None,
            ),
        )
    except HTTPException as refused:
        raise _api_errors(published, refused) from refused
    # the retention the form states, as the respondent route schedules it
    # (never fails the submission)
    try:
        if stored.expiration and stored.expiration_type not in (None, "forever"):
            await _c().temporal_service().add_scheduled_job_for_deleting_response(
                response=stored
            )
    except Exception as error:  # noqa: BLE001
        logger.error(
            "expiry job not scheduled for response {} ({})",
            stored.response_id,
            type(error).__name__,
        )
    return {
        "responseId": stored.response_id,
        "formId": str(form_id),
        "submittedAt": stored.created_at.isoformat() if stored.created_at else None,
        "formVersion": stored.form_version,
    }


async def update_submission(
    key: WorkspaceAPIKeyDocument,
    form_id: str,
    response_id: str,
    body: UpdateSubmission,
) -> Dict[str, Any]:
    from backend.config import settings

    if not settings.api_settings.ENABLE_FORM_CREATION:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="Not found")
    workspace_id = key.workspace_id
    await _workspace_form(workspace_id, form_id)
    ensure_form_allowed(key, form_id)
    try:
        RecordId(response_id)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, content="Response not found"
        )
    published = await _published(form_id)
    answers, problems = build_answers(published, body.answers)
    _refuse_problems(published, problems)
    try:
        stored = await _c().workspace_form_service().patch_response_as_key(
            workspace_id=workspace_id,
            form_id=RecordId(form_id),
            response_id=RecordId(response_id),
            response=StandardFormResponseCamelModel(answers=answers),
            key_id=str(key.id),
        )
    except HTTPException as refused:
        raise _api_errors(published, refused) from refused
    return {
        "responseId": str(response_id),
        "updatedAt": stored.updated_at.isoformat() if stored.updated_at else None,
    }
