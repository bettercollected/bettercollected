"""A section's content as a form spec fragment, and the shared validation.

A section is stored as the ``fields`` and ``containers`` of one spec page. This
module converts between that and the builder's shape (the camelCase
``StandardFormField`` the webapp holds), and validates a fragment the way a form
is validated: it is wrapped in a one-page spec document and checked by the same
``check_spec_document``, then the gates ``persist_form`` applies to a form
(switches for field rules, the newer question types, choice logic, layout
containers and option sources) are asked against an empty form, so a section can
never hold something a form could not take on this server.
"""

import json
from http import HTTPStatus
from typing import Any, Dict, List, Tuple

from common.form_spec import (
    FormSpec,
    SpecConversionError,
    form_to_spec_dict,
    spec_to_form,
)
from common.models.standard_form import StandardForm, StandardFormField
from pydantic import ValidationError

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import StandardFormFieldCamelModel
from backend.app.services.field_rules import ensure_rules_allowed
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.layout_containers import ensure_layout_allowed
from backend.app.services.new_question_types import ensure_question_types_allowed
from backend.app.services.option_logic import ensure_choice_logic_allowed
from backend.app.services.option_sources.checks import ensure_option_sources_allowed
from backend.app.services.reusable_sections import limits, refs

WRAPPER_PAGE = "section"
INVALID_CODE = "invalid_section"
TOO_LARGE_CODE = "section_too_large"
LIMIT_CODE = "limit_reached"


def refuse(status: HTTPStatus, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=status, content={"code": code, "message": message, **extra}
    )


def spec_document(
    fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]
) -> Dict[str, Any]:
    page: Dict[str, Any] = {"id": WRAPPER_PAGE, "fields": fields}
    if containers:
        page["containers"] = containers
    return {"specVersion": "1", "pages": [page]}


def _trim(value: Any) -> Any:
    """Without the ``None`` values the adapters write for every key a field does
    not use (a stored fragment keeps only what is set)."""
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for key in [k for k, v in node.items() if v is None]:
                del node[key]
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return value


def from_builder(
    fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """The builder's questions and containers (what a page holds in
    ``properties.fields`` and ``properties.containers``) as a spec fragment.
    Read like a whole-form save reads a page; a refusal is a 422."""
    raw = {
        "id": WRAPPER_PAGE,
        "type": "slide",
        "properties": {"fields": fields, "containers": containers or None},
    }
    try:
        model = StandardFormFieldCamelModel.model_validate(raw)
        page = StandardFormField(**model.model_dump(mode="json"))
        document = form_to_spec_dict(StandardForm(fields=[page]))
    except (ValidationError, ValueError, SpecConversionError) as error:
        raise refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID_CODE,
            "These questions cannot be saved as a section: "
            + _first_message(error),
        )
    spec_page = _trim(document["pages"][0])
    return spec_page.get("fields") or [], spec_page.get("containers") or []


def _first_message(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if callable(errors):
        try:
            first = errors(include_input=False, include_url=False)[0]
            where = ".".join(str(p) for p in first.get("loc", ()))
            return f"{where}: {first.get('msg')}" if where else str(first.get("msg"))
        except Exception:  # noqa: BLE001
            pass
    return str(error).splitlines()[0][:200] if str(error) else type(error).__name__


def to_form(
    fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]
) -> StandardForm:
    """The fragment as a one-page ``StandardForm`` (raises ``ValueError`` when
    the fragment is not a valid spec page)."""
    try:
        spec = FormSpec.model_validate(spec_document(fields, containers))
        return spec_to_form(spec)
    except (ValidationError, SpecConversionError) as error:
        raise ValueError(_first_message(error)) from error


def to_builder(
    fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """The fragment in the builder's shape (camelCase ``StandardFormField``s and
    ``LayoutContainer``s), ready to put on a page."""
    form = to_form(fields, containers)
    page = form.fields[0]
    props = page.properties
    out_fields = [
        StandardFormFieldCamelModel(**f.model_dump()).model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        for f in (props.fields if props else None) or []
    ]
    out_containers = [
        c.model_dump(mode="json", by_alias=True, exclude_none=True)
        for c in (props.containers if props else None) or []
    ]
    return out_fields, out_containers


def check_limits(fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]) -> None:
    count = len(refs.question_ids(fields))
    if count == 0:
        raise refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID_CODE,
            "A section needs at least one question.",
        )
    if count > limits.QUESTIONS_PER_SECTION:
        raise refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            LIMIT_CODE,
            f"A section holds at most {limits.QUESTIONS_PER_SECTION} questions.",
        )
    if len(containers) > limits.CONTAINERS_PER_SECTION:
        raise refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            LIMIT_CODE,
            f"A section holds at most {limits.CONTAINERS_PER_SECTION} layout containers.",
        )
    size = len(json.dumps([fields, containers], separators=(",", ":")).encode())
    if size > limits.CONTENT_BYTES_MAX:
        raise refuse(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            TOO_LARGE_CODE,
            f"A section is at most {limits.CONTENT_BYTES_MAX // 1000} KB.",
        )


def validate(fields: List[Dict[str, Any]], containers: List[Dict[str, Any]]) -> None:
    """The shared validation: the spec check (errors block, warnings do not),
    then the gates a form save applies. Raises a 422."""
    result = check_spec_document(spec_document(fields, containers))
    if not result["valid"]:
        errors = [
            {
                "path": e["path"].replace("/pages/0", "", 1),
                "message": e["message"],
            }
            for e in result["errors"][:50]
        ]
        raise refuse(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID_CODE,
            "This section is not valid: "
            + (errors[0]["message"] if errors else "see the errors."),
            errors=errors,
        )
    form = to_form(fields, containers)
    # a gated feature cannot enter a section either (HTTPException 422 with the
    # feature's own code)
    ensure_rules_allowed(form, None)
    ensure_layout_allowed(form, None)
    ensure_question_types_allowed(form, None)
    ensure_choice_logic_allowed(form, None)
    ensure_option_sources_allowed(form, None, answers_ok=False)


def question_types(fields: List[Dict[str, Any]]) -> Dict[str, str]:
    return {str(f["id"]): str(f.get("type")) for f in refs.questions(fields)}
