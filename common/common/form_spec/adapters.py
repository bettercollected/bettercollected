"""Explicit conversion between the form spec (public) and StandardForm
(stored).

``form_to_spec(form, settings)`` reads a page-based form, plus the trust
settings that live on its workspace association, into a ``FormSpec``.
``spec_to_form(spec)`` builds the StandardForm a writer would store and
``spec_trust_settings(spec)`` the association settings it carries.

Round trip: every value the spec covers survives StandardForm -> spec ->
StandardForm. Not covered, and so not carried over (see docs/spec/README.md):

- server-owned data: ``form_id``, ``imported_form_id``, ``type``, ``state``,
  ``published_at``, ``actions``, ``parameters``, ``secrets``, the provider
  settings (embed/custom URL, provider, visibility);
- derived data: every ``index`` (the array order is the order),
  ``builder_version`` (always "v2"), ``is_multi_page``;
- data of the first-generation builder and of imports that page-based
  forms don't use: ``tag``, ``ref`` (fields and choices), the old rule
  engine (``properties.actions``/``conditions``/``logical_operator``/
  ``update_id``/``mentions``), ``properties.hidden``, ``properties.button_text``,
  a question's own ``theme``/``layout``, the form's ``consent`` list,
  ``button_text``, ``cover_image`` and the form-level ``row_titles``/
  ``column_titles``;
- ``properties.description``, a copy of the field's ``description`` the
  editor never reads (the spec has the one description).
"""

from typing import Any, Dict, List, Optional

from common.models.standard_form import (
    StandardForm,
    StandardFormField,
    StandardFormFieldType,
)
from pydantic import ValidationError

from common.form_spec.models import (
    SPEC_VERSION,
    FormSpec,
)

PAGE_TYPE = StandardFormFieldType.SLIDE.value


class SpecConversionError(ValueError):
    """The stored form has no spec representation (or a spec document can't
    become a StandardForm). ``errors`` is a list of ``{path, message}``."""

    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors) or "Not convertible")


def _value(item: Any) -> Any:
    return getattr(item, "value", item)


# ---------------------------------------------------------------------------
# StandardForm -> spec
# ---------------------------------------------------------------------------


def _attachment_to_spec(attachment) -> Optional[Dict[str, Any]]:
    if attachment is None:
        return None
    return {
        "type": _value(attachment.type),
        "href": attachment.href,
        "scale": attachment.scale,
        "description": (
            attachment.properties.description if attachment.properties else None
        ),
        "embedProvider": _value(attachment.embed_provider),
    }


def _conditions_to_spec(conditions) -> Optional[List[Dict[str, Any]]]:
    if conditions is None:
        return None
    return [
        {
            "fieldId": c.field_id,
            "fieldType": c.field_type,
            "comparison": c.comparison,
            "value": c.value,
            "groupMode": c.group_mode,
            "childFieldId": c.child_field_id,
            "childFieldType": c.child_field_type,
        }
        for c in conditions
    ]


def _theme_to_spec(theme) -> Optional[Dict[str, Any]]:
    if theme is None:
        return None
    return theme.model_dump()


def _field_to_spec(field: StandardFormField) -> Dict[str, Any]:
    p = field.properties
    v = field.validations
    data: Dict[str, Any] = {
        "id": field.id,
        "type": _value(field.type),
        "title": field.title,
        "description": (
            field.description
            if field.description is not None
            else (p.description if p else None)
        ),
        "value": field.value,
        "imageUrl": field.image_url,
        "attachment": _attachment_to_spec(field.attachment),
        "internal": field.internal,
    }
    if v is not None:
        validations = {
            "required": v.required,
            "minLength": v.min_length,
            "maxLength": v.max_length,
            "minValue": v.min_value,
            "maxValue": v.max_value,
            "pattern": v.regex,
            "minChoices": v.min_choices,
            "maxChoices": v.max_choices,
        }
        if any(x is not None for x in validations.values()):
            data["validations"] = validations
    if p is not None:
        data.update(
            {
                "placeholder": p.placeholder,
                "choices": (
                    [
                        {
                            "id": c.id,
                            "value": c.value,
                            "label": c.label,
                            "attachment": _attachment_to_spec(c.attachment),
                        }
                        for c in p.choices
                    ]
                    if p.choices is not None
                    else None
                ),
                "allowMultipleSelection": p.allow_multiple_selection,
                "allowOtherChoice": p.allow_other_choice,
                "steps": p.steps,
                "startFrom": p.start_from,
                "ratingShape": p.rating_shape,
                "hideMarks": p.hide_marks,
                "labels": p.labels,
                "dateFormat": p.date_format,
                "rowTitles": p.row_titles,
                "columnTitles": p.column_titles,
                "tabularValue": p.tabular_value,
                "colSpan": p.col_span,
                "label": p.label,
                "dateRules": (
                    [
                        {
                            "comparison": r.comparison,
                            "target": r.target,
                            "date": r.date,
                            "fieldId": r.field_id,
                        }
                        for r in p.date_rules
                    ]
                    if p.date_rules is not None
                    else None
                ),
                "whyWeAsk": p.why_we_ask,
                "logic": (
                    {
                        "action": p.logic.action,
                        "operator": p.logic.operator,
                        "conditions": _conditions_to_spec(p.logic.conditions),
                    }
                    if p.logic is not None
                    else None
                ),
                "repeat": (
                    p.repeat.model_dump(by_alias=True) if p.repeat is not None else None
                ),
            }
        )
        # A group's questions; other types keep no (empty) children list.
        if _value(field.type) == StandardFormFieldType.GROUP.value or p.fields:
            data["fields"] = [_field_to_spec(child) for child in p.fields or []]
    return data


def _page_to_spec(page: StandardFormField) -> Dict[str, Any]:
    p = page.properties
    return {
        "id": page.id,
        "sectionTitle": p.section_title if p else None,
        "layout": _value(p.layout) if p else None,
        "imageUrl": page.image_url,
        "theme": _theme_to_spec(p.theme) if p else None,
        "showQuestionNumbers": p.show_question_numbers if p else None,
        "position": p.position.model_dump() if p and p.position else None,
        "jumps": (
            [
                {
                    "operator": j.operator,
                    "conditions": _conditions_to_spec(j.conditions),
                    "target": j.target,
                }
                for j in p.jumps
            ]
            if p and p.jumps is not None
            else None
        ),
        "fields": [_field_to_spec(f) for f in (p.fields if p else None) or []],
    }


def _retention_to_spec(kind, value) -> Optional[Dict[str, Any]]:
    kind = _value(kind)
    if not kind:
        return None
    if kind == "days" and isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    return {"type": kind, "value": value}


def _trust_to_spec(form: StandardForm, settings: Any) -> Optional[Dict[str, Any]]:
    """The trust block: from the workspace association's settings when
    given (where they are authoritative), else from the form's own."""
    own = form.settings
    if settings is not None:
        get = lambda key: getattr(settings, key, None)  # noqa: E731
    else:
        get = lambda key: getattr(own, key, None) if own else None  # noqa: E731
    trust = {
        "purpose": get("purpose"),
        "retentionText": get("retention_text"),
        "privacyPolicyUrl": get("privacy_policy_url"),
        "retention": _retention_to_spec(
            get("response_expiration_type"), get("response_expiration")
        ),
        "requireVerifiedIdentity": get("require_verified_identity"),
        "allowEditingResponse": get("allow_editing_response"),
        "showSubmissionNumber": get("show_submission_number"),
    }
    if all(v is None for v in trust.values()):
        return None
    return trust


def form_to_spec_dict(form: StandardForm, settings: Any = None) -> Dict[str, Any]:
    """The spec document of ``form`` as plain JSON-ready data (validated)."""
    return form_to_spec(form, settings).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )


def form_to_spec(form: StandardForm, settings: Any = None) -> FormSpec:
    """``form`` (page-based) as a spec document. ``settings``: the form's
    workspace association settings, for the trust block."""
    top = form.fields or []
    not_pages = [i for i, field in enumerate(top) if _value(field.type) != PAGE_TYPE]
    if not_pages:
        raise SpecConversionError(
            [
                {
                    "path": f"/fields/{not_pages[0]}",
                    "message": "This form is not built from pages (an imported or "
                    "first-generation form), so it has no spec representation.",
                }
            ]
        )
    welcome = form.welcome_page
    data = {
        "specVersion": SPEC_VERSION,
        "title": form.title,
        "description": form.description,
        "welcomePage": (
            {
                "title": welcome.title,
                "description": welcome.description,
                "layout": _value(welcome.layout),
                "imageUrl": welcome.imageUrl,
                "buttonText": welcome.buttonText,
            }
            if welcome is not None
            else None
        ),
        "pages": [_page_to_spec(page) for page in top],
        "endings": (
            [
                {
                    "title": e.title,
                    "message": e.message,
                    "buttonText": e.buttonText,
                    "buttonLink": e.buttonLink,
                    "layout": _value(e.layout),
                    "imageUrl": e.imageUrl,
                }
                for e in form.thankyou_page
            ]
            if form.thankyou_page is not None
            else None
        ),
        "theme": _theme_to_spec(form.theme),
        "hiddenFields": form.hidden_fields,
        "logo": None,
        "trust": _trust_to_spec(form, settings),
    }
    logo = {
        "url": form.logo,
        "position": form.logo_position,
        "alt": form.logo_alt,
        "useWorkspaceLogo": form.use_workspace_logo,
    }
    if any(v is not None for v in logo.values()):
        data["logo"] = logo
    try:
        return FormSpec.model_validate(data)
    except ValidationError as error:
        raise SpecConversionError(validation_errors(error)) from error


# ---------------------------------------------------------------------------
# spec -> StandardForm
# ---------------------------------------------------------------------------


def _attachment_from_spec(attachment) -> Optional[Dict[str, Any]]:
    if attachment is None:
        return None
    return {
        "type": attachment.type,
        "href": attachment.href,
        "scale": attachment.scale,
        "properties": {"description": attachment.description},
        "embed_provider": attachment.embed_provider,
    }


def _conditions_from_spec(conditions) -> Optional[List[Dict[str, Any]]]:
    if conditions is None:
        return None
    return [c.model_dump() for c in conditions]


def _field_from_spec(field, index: int) -> Dict[str, Any]:
    v = field.validations
    properties: Dict[str, Any] = {
        "placeholder": field.placeholder,
        "choices": (
            [
                {
                    "id": c.id,
                    "value": c.value,
                    "label": c.label,
                    "attachment": _attachment_from_spec(c.attachment),
                }
                for c in field.choices
            ]
            if field.choices is not None
            else None
        ),
        "allow_multiple_selection": field.allow_multiple_selection,
        "allow_other_choice": field.allow_other_choice,
        "steps": field.steps,
        "start_from": field.start_from,
        "rating_shape": field.rating_shape,
        "hide_marks": field.hide_marks,
        "labels": field.labels,
        "date_format": field.date_format,
        "row_titles": field.row_titles,
        "column_titles": field.column_titles,
        "tabular_value": field.tabular_value,
        "col_span": field.col_span,
        "label": field.label,
        "date_rules": (
            [r.model_dump() for r in field.date_rules]
            if field.date_rules is not None
            else None
        ),
        "why_we_ask": field.why_we_ask,
        "logic": (
            {
                "action": field.logic.action,
                "operator": field.logic.operator,
                "conditions": _conditions_from_spec(field.logic.conditions),
            }
            if field.logic is not None
            else None
        ),
        "repeat": field.repeat.model_dump() if field.repeat is not None else None,
        "fields": [
            _field_from_spec(child, i) for i, child in enumerate(field.fields or [])
        ],
    }
    return {
        "id": field.id,
        "index": index,
        "type": field.type,
        "title": field.title,
        "description": field.description,
        "value": field.value,
        "image_url": field.image_url,
        "attachment": _attachment_from_spec(field.attachment),
        "internal": field.internal,
        "properties": properties,
        "validations": {
            "required": v.required if v else None,
            "min_length": v.min_length if v else None,
            "max_length": v.max_length if v else None,
            "min_value": v.min_value if v else None,
            "max_value": v.max_value if v else None,
            "regex": v.pattern if v else None,
            "min_choices": v.min_choices if v else None,
            "max_choices": v.max_choices if v else None,
        },
    }


def _page_from_spec(page, index: int) -> Dict[str, Any]:
    return {
        "id": page.id,
        "index": index,
        "type": PAGE_TYPE,
        "image_url": page.image_url,
        "properties": {
            "section_title": page.section_title,
            "layout": page.layout,
            "theme": page.theme.model_dump(by_alias=True) if page.theme else None,
            "show_question_numbers": page.show_question_numbers,
            "position": page.position.model_dump() if page.position else None,
            "jumps": (
                [
                    {
                        "operator": j.operator,
                        "conditions": _conditions_from_spec(j.conditions),
                        "target": j.target,
                    }
                    for j in page.jumps
                ]
                if page.jumps is not None
                else None
            ),
            "fields": [_field_from_spec(f, i) for i, f in enumerate(page.fields)],
        },
    }


def _retention_from_spec(retention) -> tuple:
    if retention is None:
        return None, None
    value = retention.value
    return retention.type, (str(value) if value is not None else None)


def spec_to_form(spec: FormSpec) -> StandardForm:
    """The StandardForm a spec document describes (``builder_version`` v2,
    indexes from the array order). Model-level rules (repeating groups, date
    rules on date questions) apply: a breach raises SpecConversionError."""
    welcome = spec.welcome_page
    retention_type, retention_value = _retention_from_spec(
        spec.trust.retention if spec.trust else None
    )
    data = {
        "builder_version": "v2",
        "title": spec.title,
        "description": spec.description,
        "welcome_page": (
            {
                "title": welcome.title,
                "description": welcome.description,
                "layout": welcome.layout,
                "imageUrl": welcome.image_url,
                "buttonText": welcome.button_text,
            }
            if welcome is not None
            else None
        ),
        "fields": [_page_from_spec(page, i) for i, page in enumerate(spec.pages)],
        "thankyou_page": (
            [
                {
                    "title": e.title,
                    "message": e.message,
                    "buttonText": e.button_text,
                    "buttonLink": e.button_link,
                    "layout": e.layout,
                    "imageUrl": e.image_url,
                }
                for e in spec.endings
            ]
            if spec.endings is not None
            else None
        ),
        "theme": spec.theme.model_dump(by_alias=True) if spec.theme else None,
        "hidden_fields": spec.hidden_fields,
        "logo": spec.logo.url if spec.logo else None,
        "logo_position": spec.logo.position if spec.logo else None,
        "logo_alt": spec.logo.alt if spec.logo else None,
        "use_workspace_logo": spec.logo.use_workspace_logo if spec.logo else None,
        "settings": {
            "privacy_policy_url": (
                spec.trust.privacy_policy_url if spec.trust else None
            ),
            "response_expiration_type": retention_type,
            "response_expiration": retention_value,
        },
    }
    try:
        return StandardForm.model_validate(data)
    except ValidationError as error:
        raise SpecConversionError(_form_errors(error)) from error


def spec_trust_settings(spec: FormSpec) -> Dict[str, Any]:
    """The workspace-association settings the trust block sets, snake_case
    keys, only those present."""
    if spec.trust is None:
        return {}
    trust = spec.trust
    retention_type, retention_value = _retention_from_spec(trust.retention)
    values = {
        "purpose": trust.purpose,
        "retention_text": trust.retention_text,
        "privacy_policy_url": trust.privacy_policy_url,
        "response_expiration_type": retention_type,
        "response_expiration": retention_value,
        "require_verified_identity": trust.require_verified_identity,
        "allow_editing_response": trust.allow_editing_response,
        "show_submission_number": trust.show_submission_number,
    }
    return {k: v for k, v in values.items() if v is not None}


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------


def json_path(loc) -> str:
    """A pydantic error location as a JSON pointer into the document."""
    parts = []
    for part in loc:
        # union/tagged-union members show up as type names: not part of the path
        if isinstance(part, str) and (
            part in ("str", "int", "float", "bool")
            or part.startswith(("function-", "dict[", "list[", "union["))
        ):
            continue
        parts.append(str(part))
    return "/" + "/".join(parts) if parts else ""


def validation_errors(error: ValidationError) -> List[Dict[str, str]]:
    seen = set()
    errors = []
    for e in error.errors():
        message = str(e.get("msg", "")).removeprefix("Value error, ")
        if e.get("type") == "extra_forbidden":
            message = "Unknown property."
        elif e.get("type") == "missing":
            message = "This property is required."
        path = json_path(e.get("loc", ()))
        if (path, message) in seen:
            continue
        seen.add((path, message))
        errors.append({"path": path, "message": message})
    return errors


def _form_errors(error: ValidationError) -> List[Dict[str, str]]:
    """StandardForm errors, located in spec terms as far as possible
    (``fields.N.properties.fields.M`` -> ``/pages/N/fields/M``)."""
    errors = []
    for e in error.errors():
        loc = list(e.get("loc", ()))
        path: List[str] = []
        if loc[:1] == ["fields"] and len(loc) > 1:
            path = ["pages", str(loc[1])]
            rest = loc[2:]
            while rest[:3] and rest[:2] == ["properties", "fields"] and len(rest) > 2:
                path += ["fields", str(rest[2])]
                rest = rest[3:]
        message = str(e.get("msg", "")).removeprefix("Value error, ")
        errors.append(
            {"path": "/" + "/".join(path) if path else "", "message": message}
        )
    return errors
