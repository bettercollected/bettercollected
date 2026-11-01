"""Action conditions: a webhook or an email action runs only when a condition
on the submitted answers holds, read from the form's logic model and evaluated
on the server when the submission is queued."""

import json

import pytest
from common.models.standard_form import FieldLogicCondition

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.webhook import ActionCondition, LogStatus
from backend.app.services import action_conditions
from backend.app.services.email_actions.service import EmailActionUpdateDto
from backend.app.services.webhooks.service import WebhookUpdateDto
from tests.app.controllers.data import testUser
from tests.app.email_actions.helpers import condition, logs_of, make_action
from tests.app.registration.helpers import ANSWERS, publish, submit
from tests.app.webhooks.helpers import logs_of as webhook_logs
from tests.app.webhooks.helpers import make_webhook

pytestmark = pytest.mark.asyncio


def c(field, comparison, value=None, **kw):
    return FieldLogicCondition(field_id=field, comparison=comparison, value=value, **kw)


@pytest.fixture(autouse=True)
def switched_on(emails_on, transport, memory_jobs, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings.webhooks, "ENABLED", True)


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


# ------------------------------------------------------------------- saving


async def test_a_condition_is_saved_with_the_types_of_the_form(workspace):
    form = await publish(workspace)
    created = await make_action(
        workspace, form,
        condition=condition(c("age", "GREATER_THAN_EQUAL", 18, field_type="short_text"), c("colour", "IS_EQUAL", "Green")),
    )
    types = {x.field_id: x.field_type for x in created.condition.conditions}
    assert types == {"age": "number", "colour": "multiple_choice"}  # written from the form, not the request


async def test_an_empty_condition_is_no_condition(workspace):
    form = await publish(workspace)
    created = await make_action(workspace, form, condition=ActionCondition(operator="OR", conditions=[]))
    assert created.condition is None


@pytest.mark.parametrize(
    "bad",
    [
        c("nope", "IS_EQUAL", "x"),
        c("age", "SOUNDS_LIKE", "x"),
        c("upload", "IS_NOT_EMPTY"),
        c("intro", "IS_EMPTY"),
        c("people", "IS_EQUAL", "1"),  # a group needs COUNT / ANY / ALL
        c("people", "IS_EQUAL", "1", group_mode="ANY", child_field_id="missing"),
        c("name", "IS_EQUAL", "x", group_mode="COUNT"),
        c("pname", "IS_EQUAL", "x"),  # inside a group: use the group
        c("name", "IS_EQUAL", "x" * 3000),
    ],
)
async def test_a_condition_that_cannot_be_kept_is_refused(workspace, bad):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, condition=condition(bad)))
    assert error.status_code == 422 and error.content["code"] == "invalid_condition"


async def test_at_most_ten_conditions(workspace):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, condition=condition(*[c("name", "IS_NOT_EMPTY")] * 11)))
    assert error.content["code"] == "invalid_condition"


async def test_group_conditions_are_kept(workspace):
    form = await publish(workspace)
    created = await make_action(
        workspace, form,
        condition=condition(c("people", "GREATER_THAN_EQUAL", 2, group_mode="COUNT"),
                            c("people", "IS_EQUAL", "Bo", group_mode="ANY", child_field_id="pname")),
    )
    assert [x.child_field_type for x in created.condition.conditions] == [None, "short_text"]


async def test_update_sets_changes_and_removes_a_condition(workspace):
    form = await publish(workspace)
    created = await make_action(workspace, form)
    service = container.email_action_service()
    with_cond = await service.update_action(
        workspace.id, form.form_id, created.id,
        EmailActionUpdateDto(condition=condition(c("age", "GREATER_THAN", 30))), testUser)
    assert with_cond.condition.conditions[0].value == 30
    untouched = await service.update_action(
        workspace.id, form.form_id, created.id, EmailActionUpdateDto(name="Renamed"), testUser)
    assert untouched.condition is not None  # absent: kept
    removed = await service.update_action(
        workspace.id, form.form_id, created.id, EmailActionUpdateDto(condition=None), testUser)
    assert removed.condition is None


async def test_a_webhook_takes_a_condition_the_same_way(workspace, public_dns_on):
    form = await publish(workspace)
    hook = await make_webhook(workspace, form, condition=condition(c("age", "GREATER_THAN", 30)))
    assert hook.condition.conditions[0].field_type == "number"
    assert (await refused(make_webhook(workspace, form, ["name"], condition=condition(c("nope", "IS_EMPTY"))))).content["code"] == "invalid_condition"
    updated = await container.webhook_service().update_webhook(
        workspace.id, form.form_id, hook.id, WebhookUpdateDto(condition=None), testUser)
    assert updated.condition is None
    audit = await container.webhook_service().list_audit(workspace.id, form.form_id, testUser)
    assert any(a.changed == ["condition"] for a in audit)


# --------------------------------------------------------------- evaluating


async def queued(form, response, workspace):
    rows = [r for r in await logs_of(form) if r.response_id == response.response_id]
    return rows


async def test_an_email_action_runs_only_when_its_condition_holds(workspace, memory_jobs):
    form = await publish(workspace)
    await make_action(workspace, form, condition=condition(c("age", "GREATER_THAN_EQUAL", 18)))
    adult = await submit(workspace, form)  # age 36
    minor = await submit(
        workspace, form, answers={**ANSWERS, "age": {"type": "number", "number": 12}})
    (held,) = await queued(form, adult, workspace)
    (skipped,) = await queued(form, minor, workspace)
    assert held.status is LogStatus.PENDING
    assert skipped.status is LogStatus.CANCELLED and skipped.last_error_code == "condition_not_met"
    assert skipped.finished_at is not None
    assert len(memory_jobs.jobs) == 1  # only the one that holds is queued
    dumped = json.dumps(skipped.model_dump(mode="json"))
    assert "Ada" not in dumped


async def test_and_or_and_choice_conditions(workspace, memory_jobs):
    form = await publish(workspace)
    await make_action(
        workspace, form,
        condition=condition(c("colour", "IS_EQUAL", "Green"), c("age", "LESS_THAN", 10), operator="OR"))
    both_false = await submit(workspace, form, answers={**ANSWERS, "colour": {"type": "choice", "choice": {"value": "c1"}}})
    one_true = await submit(workspace, form)  # colour c2 = Green
    assert (await queued(form, both_false, workspace))[0].status is LogStatus.CANCELLED
    assert (await queued(form, one_true, workspace))[0].status is LogStatus.PENDING
    form2 = await publish(workspace)
    await make_action(
        workspace, form2,
        condition=condition(c("colour", "IS_EQUAL", "Green"), c("age", "LESS_THAN", 10)))
    only_one = await submit(workspace, form2)
    assert (await queued(form2, only_one, workspace))[0].last_error_code == "condition_not_met"


async def test_a_group_condition_counts_the_items(workspace, memory_jobs):
    form = await publish(workspace)
    await make_action(workspace, form, condition=condition(c("people", "GREATER_THAN_EQUAL", 3, group_mode="COUNT")))
    two = await submit(workspace, form)  # two people
    assert (await queued(form, two, workspace))[0].status is LogStatus.CANCELLED


async def test_an_empty_answer_is_read_as_empty(workspace, memory_jobs):
    form = await publish(workspace)
    await make_action(workspace, form, condition=condition(c("story", "IS_EMPTY")))
    filled = await submit(workspace, form)
    blank = await submit(workspace, form, answers={k: v for k, v in ANSWERS.items() if k != "story"})
    assert (await queued(form, filled, workspace))[0].status is LogStatus.CANCELLED
    assert (await queued(form, blank, workspace))[0].status is LogStatus.PENDING


async def test_a_condition_that_cannot_be_read_never_runs_the_action(workspace, memory_jobs):
    form = await publish(workspace)
    created = await make_action(workspace, form, condition=condition(c("age", "GREATER_THAN", 1)))
    # the question disappears from the form after the action was saved
    stored = await container.email_action_service()._actions.get(workspace.id, form.form_id, created.id)
    stored.condition = condition(c("removed_question", "IS_EMPTY"))
    await container.form_email_action_repo().save(stored)
    response = await submit(workspace, form)
    (row,) = await queued(form, response, workspace)
    assert row.status is LogStatus.CANCELLED and row.last_error_code == "condition_invalid"
    assert len(memory_jobs.jobs) == 0


def test_conditions_hold_reads_the_stored_answers_and_fails_closed():
    class Form:
        fields = []

    assert action_conditions.conditions_hold(None, Form(), {}) == (True, None)
    assert action_conditions.conditions_hold(ActionCondition(), Form(), {}) == (True, None)
    runs, code = action_conditions.conditions_hold(condition(c("x", "IS_EMPTY")), Form(), {})
    assert (runs, code) == (False, "condition_invalid")
    assert action_conditions.conditions_hold(condition(c("x", "IS_EMPTY")), None, {}) == (False, "condition_invalid")


async def test_a_webhook_condition_decides_whether_a_delivery_is_queued(workspace, public_dns_on, memory_jobs):
    form = await publish(workspace)
    await make_webhook(workspace, form, condition=condition(c("age", "GREATER_THAN", 30)))
    yes = await submit(workspace, form)
    no = await submit(workspace, form, answers={**ANSWERS, "age": {"type": "number", "number": 5}})
    rows = {r.response_id: r for r in await webhook_logs(form)}
    assert rows[yes.response_id].status is LogStatus.PENDING
    assert rows[no.response_id].status is LogStatus.CANCELLED
    assert rows[no.response_id].last_error_code == "condition_not_met"
    assert {j["task_name"] for j in memory_jobs.jobs.values()} == {"deliver_webhook"} and len(memory_jobs.jobs) == 1
    # the job of a not-met row is never run: nothing to claim
    assert (await container.webhook_service().run_delivery(str(rows[no.response_id].id))).status == "skipped"


async def test_a_not_met_row_is_replayed_as_a_no_op(workspace, memory_jobs):
    form = await publish(workspace)
    await make_action(workspace, form, condition=condition(c("age", "GREATER_THAN", 99)))
    response = await submit(workspace, form)
    again = await container.email_action_service().queue_for_submission(
        workspace.id, form.form_id, response.response_id, form=None, answers={})
    assert again == [] and len(await queued(form, response, workspace)) == 1
    (row,) = await queued(form, response, workspace)
    assert (await container.email_action_service().run_delivery(str(row.id))).status == "skipped"


# ----------------------------------------------- the newer question types


NEWER = [
    {"id": "labels", "type": "tags", "title": "Labels"},
    {"id": "stay", "type": "date_range", "title": "Stay"},
    {"id": "price", "type": "currency", "title": "Price"},
    {"id": "at", "type": "time", "title": "At"},
    {
        "id": "trips",
        "type": "group",
        "title": "Trips",
        "properties": {
            "repeat": {"minItems": 0, "maxItems": 3, "itemLabel": "Trip"},
            "fields": [
                {"id": "tlabels", "type": "tags", "title": "Trip labels"},
                {"id": "tstay", "type": "date_range", "title": "Trip stay"},
            ],
        },
    },
]
TAGS_OK = ("CONTAINS", "DOES_NOT_CONTAIN", "IS_EMPTY", "IS_NOT_EMPTY")
RANGE_OK = ("CONTAINS", "DOES_NOT_CONTAIN", "GREATER_THAN", "LESS_THAN", "IS_EMPTY", "IS_NOT_EMPTY")


def newer_form():
    from common.models.standard_form import StandardForm

    from tests.app.registration.helpers import FIELDS

    return StandardForm(
        builder_version="v2",
        title="t",
        fields=[{"id": "s1", "type": "slide", "properties": {"fields": [*FIELDS, *NEWER]}}],
    )


def checked(*items):
    return action_conditions.checked_condition(newer_form(), condition(*items))


def refuses(*items):
    with pytest.raises(HTTPException) as raised:
        checked(*items)
    assert raised.value.status_code == 422 and raised.value.content["code"] == "invalid_condition"


@pytest.mark.parametrize("comparison", TAGS_OK)
def test_a_tags_condition_keeps_each_comparison_that_can_fire(comparison):
    kept = checked(c("labels", comparison, "x"))
    assert kept.conditions[0].comparison == comparison and kept.conditions[0].field_type == "tags"


@pytest.mark.parametrize("comparison", RANGE_OK)
def test_a_date_range_condition_keeps_each_comparison_that_can_fire(comparison):
    kept = checked(c("stay", comparison, "2026-01-31"))
    assert kept.conditions[0].comparison == comparison and kept.conditions[0].field_type == "date_range"


@pytest.mark.parametrize("comparison", ["IS_EQUAL", "IS_NOT_EQUAL", "GREATER_THAN", "STARTS_WITH"])
def test_a_tags_condition_refuses_a_comparison_that_never_fires(comparison):
    refuses(c("labels", comparison, "x"))


@pytest.mark.parametrize("comparison", ["IS_EQUAL", "IS_NOT_EQUAL", "GREATER_THAN_EQUAL", "STARTS_WITH"])
def test_a_date_range_condition_refuses_a_comparison_that_never_fires(comparison):
    refuses(c("stay", comparison, "2026-01-31"))


@pytest.mark.parametrize("mode", ["ANY", "ALL"])
@pytest.mark.parametrize(
    "child, allowed, refused_one",
    [("tlabels", TAGS_OK, "IS_EQUAL"), ("tstay", RANGE_OK, "IS_EQUAL")],
)
def test_a_group_child_condition_follows_the_children_type(mode, child, allowed, refused_one):
    for comparison in allowed:
        kept = checked(c("trips", comparison, "x", group_mode=mode, child_field_id=child))
        assert kept.conditions[0].child_field_type in ("tags", "date_range")
    refuses(c("trips", refused_one, "x", group_mode=mode, child_field_id=child))
    # COUNT reads the number of items: a numeric comparison is fine there
    kept = checked(c("trips", "GREATER_THAN_EQUAL", 1, group_mode="COUNT"))
    assert kept.conditions[0].group_mode == "COUNT"


def test_currency_and_time_conditions_take_every_known_comparison():
    for field in ("price", "at"):
        for comparison in ("IS_EQUAL", "GREATER_THAN", "IS_NOT_EMPTY"):
            assert checked(c(field, comparison, "1")).conditions[0].comparison == comparison


@pytest.fixture()
def newer_types(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)


async def test_the_service_and_a_webhook_refuse_the_same_comparisons(workspace, newer_types, public_dns_on):
    from tests.app.registration.helpers import FIELDS

    form = await publish(workspace, fields=[*FIELDS, *NEWER])
    for make in (make_action, make_webhook):
        error = await refused(make(workspace, form, condition=condition(c("labels", "IS_EQUAL", "x"))))
        assert error.status_code == 422 and error.content["code"] == "invalid_condition"
    kept = await make_webhook(workspace, form, condition=condition(c("labels", "CONTAINS", "x")))
    assert kept.condition.conditions[0].field_type == "tags"


def test_these_conditions_read_the_stored_answers():
    form = newer_form()
    answers = {
        "labels": {"type": "tags", "tags": ["alpha", "beta"]},
        "stay": {"type": "date_range", "date_range": {"start": "2026-01-31", "end": "2026-02-03"}},
        "price": {"type": "currency", "currency": {"code": "USD", "amount": "12.50"}},
        "trips": {"type": "group", "items": [{"tlabels": {"tags": ["x"]}}, {"tlabels": {"tags": ["y", "z"]}}]},
    }

    def holds(*items):
        runs, _code = action_conditions.conditions_hold(checked(*items), form, answers)
        return runs

    assert holds(c("labels", "CONTAINS", "alpha"))
    assert not holds(c("labels", "CONTAINS", "gamma"))
    assert holds(c("labels", "DOES_NOT_CONTAIN", "gamma"))
    assert holds(c("labels", "IS_NOT_EMPTY")) and not holds(c("labels", "IS_EMPTY"))
    assert holds(c("stay", "IS_NOT_EMPTY")) and not holds(c("at", "IS_NOT_EMPTY"))
    # a currency compares its amount only: the code is ignored, and IS_EQUAL is a text comparison
    assert holds(c("price", "IS_EQUAL", "12.50"))
    assert not holds(c("price", "IS_EQUAL", "12.5"))
    assert not holds(c("price", "IS_EQUAL", "USD 12.50"))
    # a group: ANY item has the tag; ALL items must
    assert holds(c("trips", "CONTAINS", "z", group_mode="ANY", child_field_id="tlabels"))
    assert not holds(c("trips", "CONTAINS", "z", group_mode="ALL", child_field_id="tlabels"))
    assert holds(c("trips", "IS_NOT_EMPTY", group_mode="ALL", child_field_id="tlabels"))
