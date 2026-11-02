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
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.constants.consents import default_consents
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.form_availability import ensure_accepting_responses
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
MAX_CONSENT_ITEMS = 50
UNKNOWN_CONSENT_ITEM = "unknown_consent_item"


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
    consent: Optional[StrictBool] = Field(
        None,
        description="true: you assert that the respondent has given the "
        "consent the form requires (its required items). Needed when the form "
        "has a required consent item; it is recorded as asserted by this API "
        "key. Optional items are accepted only when named in consentItems.",
    )
    consent_items: Optional[List[str]] = Field(
        None,
        max_length=MAX_CONSENT_ITEMS,
        description="The ids of the form's optional consent items the "
        "respondent accepted. Ids the form does not have are refused (422); "
        "optional items not named are stored as not accepted.",
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


# a submission's JSON nests at most this deep (answers, a typed answer, a
# group's items, an item's answer, a slot): deeper is never a real answer
MAX_BODY_DEPTH = 12


def _too_deep(value: Any, limit: int = MAX_BODY_DEPTH) -> bool:
    """Whether ``value`` nests deeper than ``limit`` (iterative: a crafted
    body can't recurse the checker)."""
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, (dict, list)):
            if depth > limit:
                return True
            children = item.values() if isinstance(item, dict) else item
            stack.extend((child, depth + 1) for child in children)
    return False


def parse_body(model: type, raw: Any):
    """The request body as ``model``, 422 ``invalid_request`` with the
    problem's JSON pointer when it does not fit."""
    if not isinstance(raw, dict):
        raise _invalid("invalid_request", "The body must be a JSON object.")
    if _too_deep(raw):
        raise _invalid("invalid_request", "The body is nested too deeply.")
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


def ensure_acts_as_nobody_allowed(form_settings: Any) -> None:
    """A form that asks for a verified respondent, or is limited to admitted
    responders, has someone to be: an API key is nobody (no identity, no
    receipt, no OTP), so those forms refuse it, for a new response and for a
    change to one it made."""
    if form_settings and (
        form_settings.require_verified_identity or form_settings.private
    ):
        raise _invalid(
            IDENTITY_REQUIRED,
            "This form needs a signed-in respondent, so it does not take "
            "submissions from an API key.",
        )


def _request_model(published: Any, **values: Any) -> StandardFormResponseCamelModel:
    """The respondent's request object; a body the model can't take is a 422
    (a backstop: the answers were read into typed objects before)."""
    try:
        return StandardFormResponseCamelModel(**values)
    except ValidationError as error:
        problems = []
        for e in error.errors():
            loc = e.get("loc") or ()
            key = str(loc[1]) if len(loc) > 1 and loc[0] == "answers" else ""
            problems.append(
                {"path": f"/answers/{key}", "message": "type: " + RULE_TEXT["type"]}
            )
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": ERROR_MESSAGE,
                "errors": problems,
            },
        ) from error


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
    form: Any, asserted: Optional[bool], named: Optional[List[str]] = None
) -> Optional[List[Dict[str, Any]]]:
    """The stored consent of the response, built by the server from the form's
    own items, accepting only what the caller said:

    * ``consent: true`` accepts the form's **required** items (422
      ``consent_required`` when the form has one and it was not sent);
    * an **optional** item is accepted only when its id is named in
      ``consentItems`` (an id the form does not have is 422
      ``unknown_consent_item``); the others are stored as not accepted;
    * an information item has nothing to accept.
    """
    items = _consent_items(form)
    if not items:
        return None
    required = [item for item in items if item.required]
    if required and asserted is not True:
        raise _invalid(
            CONSENT_REQUIRED,
            "This form requires the respondent's consent. Send "
            '"consent": true to assert that it has been given.',
        )
    wanted = set(named or [])
    unknown = wanted - {item.consent_id for item in items if item.consent_id}
    if unknown:
        raise _invalid(
            UNKNOWN_CONSENT_ITEM,
            "consentItems names an item this form does not have.",
        )
    stored = []
    for item in items:
        if item.type != ConsentType.CHECKBOX:
            accepted = None
        else:
            accepted = bool(
                (item.required and asserted is True)
                or (item.consent_id and item.consent_id in wanted)
            )
        stored.append(ConsentResponse(**item.model_dump(), accepted=accepted).model_dump())
    return stored


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
    "clear_not_supported": "an update can't clear an answer: send a new value",
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
    if error.status_code == HTTPStatus.UNPROCESSABLE_ENTITY and (
        isinstance(content, str) or (isinstance(content, dict) and not content.get("code"))
    ):
        # a check of the respondent path that names no question (a group
        # answer on the wrong question): the API's code, the check's text
        message = content if isinstance(content, str) else content.get("message")
        return HTTPException(
            status_code=error.status_code,
            content={
                "code": ERROR_CODE,
                "message": str(message or ERROR_MESSAGE),
            },
            headers=error.headers,
        )
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


async def _already_stored(workspace_id: RecordId, response_id: str):
    """The workspace's stored response ``response_id``, or None when it is
    not there (or cannot be looked up: the original failure stands)."""
    try:
        return await _c().form_response_service().workspace_response(
            workspace_id, response_id
        )
    except Exception:  # noqa: BLE001
        return None


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
    ensure_acts_as_nobody_allowed(association.settings)
    published = await _published(form_id)
    consent = _consent_given(published, body.consent, body.consent_items)
    answers, problems = build_answers(published, body.answers)
    _refuse_problems(published, problems)
    request = _request_model(
        published,
        answers=answers,
        hidden_fields=_hidden_values(published, body.hidden_fields) or None,
        consent=consent,
        # the version the answers are checked against, as the respondent's
        # page sends it: staff open the response in the form it was given in
        form_version=getattr(published, "version", None),
    )
    # the response's id is ours to know before anything is stored, so that a
    # failure after the commit can be told from one before it
    response_id = str(RecordId())
    try:
        stored = await _c().workspace_form_service().submit_response(
            workspace_id=workspace_id,
            form_id=RecordId(form_id),
            response=request,
            user=None,
            response_id=response_id,
            source=SubmissionSource(
                channel="api",
                key_id=str(key.id),
                key_name=key.name,
                consent_asserted=consent is not None and body.consent is True,
            ),
        )
    except HTTPException as refused:
        raise _api_errors(published, refused) from refused
    except Exception as error:  # noqa: BLE001
        # Stored already? Then the caller must be told so, never given a 5xx
        # that releases its Idempotency-Key and makes a retry store a second
        # response (and run the actions, webhooks and mails again).
        stored = await _already_stored(workspace_id, response_id)
        if stored is None:
            raise
        logger.error(
            "submission {} stored, a step after it failed ({})",
            response_id,
            type(error).__name__,
        )
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
    association = await _workspace_form(workspace_id, form_id)
    ensure_form_allowed(key, form_id)
    # the create's own gates: a machine caller can't change data on a form that
    # now needs a verified respondent, is private, is closed or is not open
    # (a respondent's edit is judged by the respondent: this one has none)
    ensure_acts_as_nobody_allowed(association.settings)
    ensure_accepting_responses(association.settings)
    try:
        RecordId(response_id)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, content="Response not found"
        )
    published = await _published(form_id)
    answers, problems = build_answers(published, body.answers, allow_null=False)
    _refuse_problems(published, problems)
    try:
        stored = await _c().workspace_form_service().patch_response_as_key(
            workspace_id=workspace_id,
            form_id=RecordId(form_id),
            response_id=RecordId(response_id),
            response=_request_model(published, answers=answers),
            key_id=str(key.id),
        )
    except HTTPException as refused:
        raise _api_errors(published, refused) from refused
    return {
        "responseId": str(response_id),
        "updatedAt": stored.updated_at.isoformat() if stored.updated_at else None,
    }
