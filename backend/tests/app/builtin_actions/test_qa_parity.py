"""``builtin_actions.qa`` gives what the actions executor's ``utilities/form.py``
gave: what webhooks, Slack, Discord, mails and Google Sheets receive.

* the golden file ``golden/qa.json`` was made from the executor's own output
  over ``cases.py`` (``regenerate_golden.py``) and stays when the executor goes;
* while the executor's file is in the repository, the same cases also run
  against it directly, so a change on either side fails here.
"""

import json
from pathlib import Path

import pytest

from backend.app.services.builtin_actions import qa
from tests.app.builtin_actions import battery, cases
from tests.app.builtin_actions.regenerate_golden import (
    EXECUTOR_FORM,
    GOLDEN,
    load_executor_form,
)


@pytest.fixture(scope="module")
def golden():
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ported():
    return battery.run(qa)


def test_the_golden_file_covers_every_case(golden):
    assert set(golden["answers"]) == {name for name, _, _ in cases.ANSWER_CASES}
    assert set(golden["forms"]) == {case["name"] for case in cases.FORM_CASES}
    assert len(golden["calculated_formats"]) == len(cases.CALCULATED_FORMATS)
    assert len(golden["formula_safe"]) == len(cases.FORMULA_STRINGS)


@pytest.mark.parametrize("name", [name for name, _, _ in cases.ANSWER_CASES])
def test_an_answer_reads_as_before(golden, ported, name):
    assert ported["answers"][name] == golden["answers"][name]


@pytest.mark.parametrize("case", [case["name"] for case in cases.FORM_CASES])
def test_a_whole_form_reads_as_before(golden, ported, case):
    expected = golden["forms"][case]
    got = ported["forms"][case]
    for key in expected:
        if key == "qa twice over the same form":
            continue  # the one deliberate difference, tested below
        assert got[key] == expected[key], key


@pytest.mark.parametrize(
    "section",
    [
        "calculated_formats",
        "address_lines",
        "formula_safe",
        "column_letters",
        "sheet_titles",
        "unique_sheet_titles",
    ],
)
def test_the_helpers_work_as_before(golden, ported, section):
    assert ported[section] == golden[section]


def test_nothing_in_the_golden_file_is_an_error_but_the_ones_pinned_on_purpose(golden):
    raised = []

    def walk(path, node):
        if isinstance(node, dict):
            if set(node) == {"raises"}:
                raised.append(path)
            for key, value in node.items():
                walk(f"{path}/{key}", value)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(f"{path}[{index}]", value)

    walk("", golden)
    assert raised == []


def test_the_input_form_is_never_changed():
    import copy

    for case in cases.FORM_CASES:
        form = copy.deepcopy(case["form"])
        qa.get_questions_and_answers(form, case["response"])
        qa.get_questions_and_answers(form, case["response"], fixed_columns=True)
        qa.get_group_tables(form, case["response"])
        assert form == case["form"]


def test_a_second_pass_over_one_form_reads_the_same(ported):
    for case, result in ported["forms"].items():
        first, second = result["qa twice over the same form"]
        assert first == second, case
        assert first == result["qa fixed_columns=False respondent=False"], case


@pytest.mark.skipif(
    not EXECUTOR_FORM.exists(), reason="the actions executor is no longer in the repository"
)
def test_the_port_matches_the_executors_own_code_today(ported):
    executor = battery.run(load_executor_form())
    for key in ("answers", "calculated_formats", "address_lines", "formula_safe",
                "column_letters", "sheet_titles", "unique_sheet_titles"):
        assert ported[key] == executor[key], key
    for name, result in executor["forms"].items():
        for part, value in result.items():
            if part == "qa twice over the same form":
                continue
            assert ported["forms"][name][part] == value, (name, part)
