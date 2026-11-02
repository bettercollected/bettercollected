"""Runs every case of ``cases.py`` through a module with the executor's
``utilities.form`` functions and returns one JSON-able result.

The golden file is this result for the executor's own module; the port must
give the same result. Inputs are deep-copied for each call: the executor's
function writes titles into the form it is given.
"""

import copy
import json
from typing import Any

from tests.app.builtin_actions import cases


def _outcome(call, *args, **kwargs) -> Any:
    """The value, or the name of the exception: both are behaviour to keep."""
    try:
        return call(*copy.deepcopy(args), **copy.deepcopy(kwargs))
    except Exception as error:  # noqa: BLE001 - the error type is the result
        return {"raises": type(error).__name__}


def _field_summary(fields):
    return [
        {"id": field.get("id"), "title": field.get("title"), "type": field.get("type")}
        for field in fields
    ]


def _fields(mod, form, **kwargs):
    return _field_summary(mod.get_fields_from_v2_form(copy.deepcopy(form), **kwargs))


def _unique_runs(mod):
    results = []
    for run in cases.UNIQUE_SHEET_TITLE_RUNS:
        used: set = set()
        results.append(
            [mod.unique_sheet_title(title, field_id, used) for title, field_id in run]
        )
    return results


def _form_case(mod, case):
    form, response = case["form"], case["response"]
    result = {
        "fields": _outcome(lambda f: _fields(mod, f), form),
        "fields_for_respondent": _outcome(
            lambda f: _fields(mod, f, respondent=True), form
        ),
        "group_tables": _outcome(mod.get_group_tables, form, response),
    }
    for fixed_columns in (False, True):
        for respondent in (False, True):
            key = f"qa fixed_columns={fixed_columns} respondent={respondent}"
            result[key] = _outcome(
                mod.get_questions_and_answers,
                form,
                response,
                fixed_columns=fixed_columns,
                respondent=respondent,
            )
    # a second pass over one form object: the executor changes titles in place,
    # the port must not change what a later pass reads
    reused = copy.deepcopy(form)
    first = _outcome(mod.get_questions_and_answers, reused, response)
    second = _outcome(mod.get_questions_and_answers, reused, response)
    result["qa twice over the same form"] = [first, second]
    return result


def run(mod) -> dict:
    out = {
        "answers": {},
        "calculated_formats": [],
        "address_lines": [],
        "formula_safe": [],
        "column_letters": [],
        "sheet_titles": [],
        "unique_sheet_titles": _unique_runs(mod),
        "forms": {},
    }
    for name, field, answer in cases.ANSWER_CASES:
        out["answers"][name] = _outcome(
            mod.get_answer_for_field, {"answers": {field["id"]: answer}}, field
        )
    for answer, fmt in cases.CALCULATED_FORMATS:
        out["calculated_formats"].append(
            _outcome(mod.format_calculated_value, answer, fmt)
        )
    for value in cases.ADDRESS_VALUES:
        out["address_lines"].append(_outcome(mod.address_line, value))
    for value in cases.FORMULA_STRINGS:
        out["formula_safe"].append(_outcome(mod.formula_safe, value))
    for count in cases.COLUMN_COUNTS:
        out["column_letters"].append(_outcome(mod.column_letter, count))
    for title in cases.SHEET_TITLES:
        out["sheet_titles"].append(_outcome(mod.sheet_title_for, title))
    for case in cases.FORM_CASES:
        out["forms"][case["name"]] = _form_case(mod, case)
    # what a receiver sees is JSON: compare it in that form
    return json.loads(json.dumps(out, ensure_ascii=False))
