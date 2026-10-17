"""Checking a form spec document: schema, structure and the same rules a
form save applies, each problem with its JSON-pointer ``path``.

``check_spec_document(raw)`` never raises for a bad document; it returns
``{valid, errors, warnings, compliance}``. Errors block a save; warnings
(publish checks, read-only values) don't.
"""

import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

from common.form_spec import (
    FormSpec,
    SpecConversionError,
    spec_to_form,
    validation_errors,
)
from common.form_spec.models import JUMP_TARGET_SUBMIT, LEGACY_FIELD_TYPES
from common.models.standard_form import date_rule_problems
from pydantic import ValidationError

from backend.app.services.image_urls import checked_image_url
from backend.app.services.policy_url import checked_button_link, checked_policy_url
from backend.app.services.publish_checks import publish_problems
from backend.app.services.retention import checked_retention

# The org's compliance rules are free text: only an AI review reads them.
COMPLIANCE_NOT_CHECKED = {
    "checked": False,
    "reason": "The organisation's compliance rules are written in plain language "
    "and are only checked by the AI review, which validation does not run. "
    "Use the AI review on a saved form for compliance findings.",
}

GROUP_MODES_WITH_CHILD = ("ANY", "ALL")


def _problem(path: str, message: str) -> Dict[str, str]:
    return {"path": path, "message": message}


class _Index:
    """Where each page and question of a spec lives."""

    def __init__(self, spec: FormSpec):
        self.pages: Dict[str, int] = {}
        # id -> (path, field, group id or None)
        self.questions: Dict[str, Tuple[str, Any, Optional[str]]] = {}
        self.errors: List[Dict[str, str]] = []
        for p, page in enumerate(spec.pages):
            path = f"/pages/{p}"
            self._claim(page.id, f"{path}/id")
            self.pages.setdefault(page.id, p)
            for f, field in enumerate(page.fields):
                field_path = f"{path}/fields/{f}"
                self._add(field, field_path, None)
                for c, child in enumerate(field.fields or []):
                    self._add(child, f"{field_path}/fields/{c}", field.id)

    def _claim(self, item_id: str, path: str) -> None:
        if item_id in self.pages or item_id in self.questions:
            self.errors.append(
                _problem(path, f"The id '{item_id}' is used more than once.")
            )

    def _add(self, field: Any, path: str, group_id: Optional[str]) -> None:
        self._claim(field.id, f"{path}/id")
        self.questions.setdefault(field.id, (path, field, group_id))


def _title(field: Any) -> str:
    if isinstance(field.title, str) and field.title.strip():
        return field.title.strip()
    return field.id


def _check_conditions(
    index: _Index,
    conditions: Any,
    path: str,
    scope_group: Optional[str],
    owner_id: Optional[str],
) -> List[Dict[str, str]]:
    """Every condition must use an existing, respondent-facing question the
    rule may see (inside a repeating group only its siblings; outside, the
    group as a whole)."""
    problems = []
    for i, condition in enumerate(conditions or []):
        here = f"{path}/conditions/{i}"
        if not condition.field_id:
            problems.append(_problem(f"{here}/fieldId", "A condition needs a fieldId."))
            continue
        if not condition.comparison:
            problems.append(
                _problem(f"{here}/comparison", "A condition needs a comparison.")
            )
        if condition.field_id == owner_id:
            problems.append(
                _problem(
                    f"{here}/fieldId",
                    "A question's visibility cannot depend on its own answer.",
                )
            )
            continue
        entry = index.questions.get(condition.field_id)
        if entry is None:
            what = "a page" if condition.field_id in index.pages else "no question"
            problems.append(
                _problem(
                    f"{here}/fieldId",
                    f"'{condition.field_id}' is {what} of this form; a condition "
                    "needs one of its questions.",
                )
            )
            continue
        _, source, source_group = entry
        if source.internal:
            problems.append(
                _problem(
                    f"{here}/fieldId",
                    f"'{_title(source)}' is an internal field: respondents never "
                    "answer it, so logic cannot depend on it.",
                )
            )
        if source_group is not None and source_group != scope_group:
            problems.append(
                _problem(
                    f"{here}/fieldId",
                    f"'{_title(source)}' is asked once per item of a repeating "
                    "group. Outside the group, refer to the group itself with "
                    "groupMode COUNT, ANY or ALL.",
                )
            )
        is_group = source.repeat is not None
        if is_group and not condition.group_mode:
            problems.append(
                _problem(
                    f"{here}/groupMode",
                    f"'{_title(source)}' is a repeating group: set groupMode to "
                    "COUNT, ANY or ALL.",
                )
            )
        elif not is_group and condition.group_mode:
            problems.append(
                _problem(
                    f"{here}/groupMode",
                    f"groupMode only applies to repeating groups, not "
                    f"'{_title(source)}'.",
                )
            )
        elif is_group and condition.group_mode in GROUP_MODES_WITH_CHILD:
            children = {child.id for child in source.fields or []}
            if condition.child_field_id not in children:
                problems.append(
                    _problem(
                        f"{here}/childFieldId",
                        f"ANY/ALL conditions need childFieldId: a question of "
                        f"'{_title(source)}'.",
                    )
                )
    return problems


def _check_logic(spec: FormSpec, index: _Index) -> List[Dict[str, str]]:
    problems = []
    for question_id, (path, field, group_id) in index.questions.items():
        if field.logic is not None:
            problems += _check_conditions(
                index, field.logic.conditions, f"{path}/logic", group_id, question_id
            )
    for p, page in enumerate(spec.pages):
        for j, jump in enumerate(page.jumps or []):
            here = f"/pages/{p}/jumps/{j}"
            if jump.target != JUMP_TARGET_SUBMIT:
                if jump.target not in index.pages:
                    problems.append(
                        _problem(
                            f"{here}/target",
                            f"'{jump.target}' is not a page of this form (use a "
                            f"page id or {JUMP_TARGET_SUBMIT}).",
                        )
                    )
                elif jump.target == page.id:
                    problems.append(
                        _problem(f"{here}/target", "A page cannot jump to itself.")
                    )
            problems += _check_conditions(index, jump.conditions, here, None, None)
    return problems


def _url_problem(check, value, path: str) -> List[Dict[str, str]]:
    if value is None:
        return []
    try:
        check(value)
    except ValueError as error:
        return [_problem(path, str(error))]
    return []


def _attachment_image(attachment, path: str):
    if attachment is not None and attachment.type == "image" and attachment.href:
        yield f"{path}/attachment/href", attachment.href


def _image_urls(spec: FormSpec, index: "_Index"):
    """``(path, url)`` of every image the document would show:
    respondent pages load them straight from these addresses."""
    if spec.welcome_page is not None:
        yield "/welcomePage/imageUrl", spec.welcome_page.image_url
    themes = [("/theme", spec.theme)]
    for p, page in enumerate(spec.pages):
        yield f"/pages/{p}/imageUrl", page.image_url
        themes.append((f"/pages/{p}/theme", page.theme))
    for path, theme in themes:
        if theme is not None and theme.background is not None:
            yield f"{path}/background/imageUrl", theme.background.image_url
    for path, field, _ in index.questions.values():
        yield f"{path}/imageUrl", field.image_url
        yield from _attachment_image(field.attachment, path)
        for c, choice in enumerate(field.choices or []):
            yield from _attachment_image(choice.attachment, f"{path}/choices/{c}")
    for i, ending in enumerate(spec.endings or []):
        yield f"/endings/{i}/imageUrl", ending.image_url


def _check_links_and_images(spec: FormSpec, index: "_Index") -> List[Dict[str, str]]:
    problems = []
    for i, ending in enumerate(spec.endings or []):
        problems += _url_problem(
            checked_button_link, ending.button_link, f"/endings/{i}/buttonLink"
        )
    for path, url in _image_urls(spec, index):
        problems += _url_problem(checked_image_url, url, path)
    trust = spec.trust
    if trust is not None:
        problems += _url_problem(
            checked_policy_url, trust.privacy_policy_url, "/trust/privacyPolicyUrl"
        )
        if trust.retention is not None:
            try:
                checked_retention(
                    trust.retention.type, trust.retention.value, dt.date.today()
                )
            except ValueError as error:
                problems.append(_problem("/trust/retention", str(error)))
    return problems


def _check_hidden_fields(spec: FormSpec) -> List[Dict[str, str]]:
    problems = []
    seen = set()
    for i, name in enumerate(spec.hidden_fields or []):
        if not name.strip():
            problems.append(
                _problem(f"/hiddenFields/{i}", "A hidden field needs a name.")
            )
        elif name in seen:
            problems.append(
                _problem(
                    f"/hiddenFields/{i}", f"The hidden field '{name}' is listed twice."
                )
            )
        seen.add(name)
    return problems


def _warnings(spec: FormSpec, form: Any, index: _Index) -> List[Dict[str, str]]:
    warnings = []
    if spec.logo is not None and spec.logo.url is not None:
        warnings.append(
            _problem(
                "/logo/url",
                "The logo is set by uploading it; a url in the document is ignored.",
            )
        )
    for path, field, _ in index.questions.values():
        if field.type in LEGACY_FIELD_TYPES:
            warnings.append(
                _problem(
                    f"{path}/type",
                    f"'{field.type}' is a legacy type the builder no longer offers; "
                    "use a current type for new questions.",
                )
            )
    for problem in publish_problems(form):
        entry = index.questions.get(problem.get("fieldId") or "")
        warnings.append(
            _problem(
                entry[0] if entry else "", f"Before publishing: {problem['message']}"
            )
        )
    return warnings


def check_spec_document(raw: Any) -> Dict[str, Any]:
    """Check a spec document; see the module docstring for the result."""
    result: Dict[str, Any] = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "compliance": dict(COMPLIANCE_NOT_CHECKED),
    }
    if not isinstance(raw, dict):
        result["errors"] = [_problem("", "The document must be a JSON object.")]
        return result
    try:
        spec = FormSpec.model_validate(raw)
    except ValidationError as error:
        result["errors"] = validation_errors(error)
        return result
    try:
        form = spec_to_form(spec)
    except SpecConversionError as error:
        result["errors"] = error.errors
        return result

    index = _Index(spec)
    errors = list(index.errors)
    errors += _check_logic(spec, index)
    errors += [_problem("", message) for message in date_rule_problems(form.fields)]
    errors += _check_links_and_images(spec, index)
    errors += _check_hidden_fields(spec)
    result["errors"] = errors
    result["valid"] = not errors
    result["warnings"] = _warnings(spec, form, index)
    return result
