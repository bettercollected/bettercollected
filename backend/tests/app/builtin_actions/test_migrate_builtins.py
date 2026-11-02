"""``python -m backend.migrate_builtins``: the built-in actions of a form become
webhooks and email actions (and the Sheets action is marked for the backend's own
runner) without a double or a lost delivery, and can be given back. Counts only
in what it prints."""

import json
from types import SimpleNamespace

import pytest
from common.models.standard_form import ActionState, ParameterValue, Trigger

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import FormActionType
from backend.app.schemas.webhook import ActionType
from backend.app.services.actions_service import entry_in_force
from backend.app.services.builtin_actions import migrate
from backend.app.services.registration import client
from backend.app.services.webhooks import formats
from backend.app.services.webhooks.sealing import unseal_url
from backend.config import settings
from backend import migrate_builtins
from tests.app.controllers.data import testUser
from tests.app.email_actions.conftest import (  # noqa: F401 - fixtures
    EMAILS,
    auth_users,
    emails_on,
    public_dns_on,
    transport,
)
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.registration.helpers import publish, submit
from tests.app.registration.tls_server import PUBLIC_ADDRESS
from tests.app.webhooks.conftest import webhooks_on  # noqa: F401

pytestmark = pytest.mark.asyncio

HOOK = "https://case.example.org/hooks/old?key=SECRET-KEY"
SLACK = "https://hooks.slack.com/services/T000/B000/token-value"
DISCORD = "https://discord.com/api/webhooks/123456/token-value"
OWNER = EMAILS[testUser.id]


@pytest.fixture(autouse=True)
def switched_on(webhooks_on, emails_on, public_dns_on):
    pass


async def builtin(name):
    return await container.action_repository().create_global_action(
        ActionDto(
            name=name,
            action_code="",
            type=FormActionType.INTERNAL.value,
            predefined=True,
        ),
        testUser,
    )


async def attach(workspace, form, specs):
    """``specs``: (action name, {parameter: value}, enabled)."""
    document = await container.form_repo().get_form_document_by_id(form.form_id)
    entries, parameters, secrets = [], {}, {}
    made = {}
    for name, params, enabled in specs:
        action = await builtin(name)
        await container.action_repository().create_action_in_workspace_from_action(
            workspace_id=workspace.id, action_id=action.id
        )
        entries.append(ActionState(id=action.id, enabled=enabled))
        parameters[str(action.id)] = [ParameterValue(name=k, value=v) for k, v in params.items()]
        if name == "integrate_google_sheets":
            parameters[str(action.id)].append(
                ParameterValue(name="Google Sheet Id", value="1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdE")
            )
            secrets[str(action.id)] = [
                ParameterValue(name="Credentials", value=container.crypto().encrypt("{}"))
            ]
        made[name] = action
    document.actions = {Trigger.on_submit: entries}
    document.parameters = parameters
    document.secrets = secrets or document.secrets
    await container.form_repo().save_form(document)
    return made


FULL = [
    ("send_webhook", {"Webhook URL": HOOK}, True),
    ("send_to_slack", {"Slack Webhook URL": SLACK}, True),
    ("send_to_discord", {"Discord Webhook URL": DISCORD}, False),
    ("creator_copy_mail", {"Receiving Mail Address": OWNER}, True),
    ("responder_copy_mail", {}, True),
    ("integrate_google_sheets", {}, True),
]


def tool():
    return migrate_builtins.migration_of(container)


async def entries_of(form):
    document = await container.form_repo().get_form_document_by_id(form.form_id)
    return {str(e.id): e for e in document.actions[Trigger.on_submit]}


async def setup(workspace, specs=FULL):
    form = await publish(workspace)
    actions = await attach(workspace, form, specs)
    return SimpleNamespace(workspace=workspace, form=form, actions=actions)


# --------------------------------------------------------------- preflight


async def test_preflight_reads_and_writes_nothing_and_prints_counts_only(workspace):
    setup_ = await setup(workspace)
    report = await tool().preflight()
    text = report.as_json()
    assert report.counts["forms_with_builtins"] == 1
    for name in migrate.BUILTINS:
        assert report.counts[f"found.{name}"] == 1
        assert report.counts[f"movable.{name}"] == 1
    assert report.counts["found.send_to_discord.disabled"] == 1
    assert report.blocked() == 0
    for secret in ("case.example.org", "SECRET-KEY", "hooks.slack.com", OWNER, "token-value"):
        assert secret not in text
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []
    assert all(not e.migrated_to for e in (await entries_of(setup_.form)).values())


async def test_what_cannot_move_is_reported_not_relaxed(workspace, monkeypatch):
    setup_ = await setup(
        workspace,
        [
            ("send_webhook", {"Webhook URL": "http://case.example.org/x"}, True),
            ("send_to_slack", {"Slack Webhook URL": "https://evil.example.org/hook"}, True),
            ("send_to_discord", {}, True),
            ("creator_copy_mail", {"Receiving Mail Address": "stranger@elsewhere.example"}, True),
            ("integrate_google_sheets", {}, True),
        ],
    )
    report = await tool().preflight()
    counts = report.counts
    assert counts["blocked.address_invalid.send_webhook"] == 1
    assert counts["blocked.host_not_allowed.send_to_slack"] == 1
    assert counts["blocked.address_missing.send_to_discord"] == 1
    assert counts["blocked.recipient_not_member.creator_copy_mail"] == 1
    assert counts["movable.integrate_google_sheets"] == 1
    assert report.blocked() == 4


async def test_an_address_that_resolves_inward_is_not_moved(workspace, monkeypatch):
    await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])

    async def inward(host, port=443):
        return ["10.0.0.7"]

    monkeypatch.setattr(client, "resolve", inward)
    report = await tool().preflight()
    assert report.counts["blocked.address_not_allowed"] == 1


async def test_an_action_nobody_had_on_is_left_as_it_is_without_blocking(workspace):
    await setup(workspace, [("send_webhook", {"Webhook URL": "http://insecure.example/x"}, False)])
    report = await tool().preflight()
    assert report.counts["not_moved.disabled.send_webhook"] == 1 and report.blocked() == 0


async def test_the_switches_and_the_mail_server_are_needed_for_what_is_on(workspace, monkeypatch):
    await setup(
        workspace,
        [
            ("send_webhook", {"Webhook URL": HOOK}, True),
            ("responder_copy_mail", {}, True),
        ],
    )
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    monkeypatch.setattr(settings.email_actions, "ENABLED", False)
    report = await tool().preflight()
    assert report.counts["blocked.switch_off.send_webhook"] == 1
    assert report.counts["blocked.switch_off.responder_copy_mail"] == 1
    monkeypatch.setattr(settings.email_actions, "ENABLED", True)
    monkeypatch.setattr(settings.mail_settings, "smtp_server", "")
    assert (await tool().preflight()).counts["blocked.mail_not_configured"] == 1


async def test_the_caps_count_what_the_form_already_has(workspace):
    from tests.app.webhooks.helpers import make_webhook

    form = await publish(workspace)
    for _ in range(5):
        await make_webhook(workspace, form, ["name"])
    await attach(workspace, form, [("send_webhook", {"Webhook URL": HOOK}, True)])
    assert (await tool().preflight()).counts["blocked.cap_exceeded"] == 1


async def test_forms_of_the_first_builder_never_ran_so_nothing_moves(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    document = await container.form_repo().get_form_document_by_id(setup_.form.form_id)
    document.builder_version = "v1"
    await container.form_repo().save_form(document)
    report = await tool().preflight()
    assert report.counts["skipped.form_v1"] == 1 and report.blocked() == 0


async def test_the_workspace_and_form_mail_server_is_dropped_and_reported(workspace):
    setup_ = await setup(workspace, [("creator_copy_mail", {"Receiving Mail Address": OWNER}, True)])
    action_id = str(setup_.actions["creator_copy_mail"].id)
    document = await container.form_repo().get_form_document_by_id(setup_.form.form_id)
    document.parameters[action_id].append(ParameterValue(name="server", value="smtp.mine.example"))
    await container.form_repo().save_form(document)
    assert (await tool().preflight()).counts["dropped.mail_server"] == 1


# ------------------------------------------------------------------- apply


async def test_apply_moves_each_action_and_marks_the_old_entry(workspace):
    setup_ = await setup(workspace)
    report = await tool().apply()
    assert report.blocked() == 0
    for name in migrate.BUILTINS:
        assert report.counts[f"moved.{name}"] == 1
    webhooks = {
        w.source_action_id: w
        for w in await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id)
    }
    by_name = {n: webhooks[str(a.id)] for n, a in setup_.actions.items() if str(a.id) in webhooks}
    legacy, slack, discord = by_name["send_webhook"], by_name["send_to_slack"], by_name["send_to_discord"]
    assert (legacy.format, slack.format, discord.format) == ("legacy_list", "slack", "discord")
    assert (legacy.enabled, slack.enabled, discord.enabled) == (True, True, False)
    assert legacy.host == "case.example.org" and slack.host == "hooks.slack.com"
    assert legacy.created_via == "migrated_builtin" and legacy.fields == []
    crypto = container.crypto()
    assert unseal_url(crypto, workspace.id, legacy.id, legacy.url_sealed) == HOOK
    assert legacy.secret_sealed and slack.secret_sealed is None and discord.secret_sealed is None
    emails = await container.form_email_action_repo().list_for_form(workspace.id, setup_.form.form_id)
    by_source = {e.source_action_id: e for e in emails}
    creator = by_source[str(setup_.actions["creator_copy_mail"].id)]
    responder = by_source[str(setup_.actions["responder_copy_mail"].id)]
    assert creator.team_recipients == [OWNER] and creator.respondent_copy is False
    assert responder.team_recipients == [] and responder.respondent_copy is True
    assert creator.all_questions and responder.all_questions and creator.enabled
    assert creator.en.subject == "You have got a new response in {{form_title}}"
    assert "View all responses:" in creator.en.body and "/dashboard/forms/" in creator.en.body
    entries = await entries_of(setup_.form)
    for name, action in setup_.actions.items():
        entry = entries[str(action.id)]
        assert entry.migrated_to and entry.migrated_at
        assert entry.migrated_to["kind"] == ("sheets" if name == "integrate_google_sheets" else (
            "webhook" if name in migrate.WEBHOOK_OF else "email"))
        # the old action never runs next to the new one; Sheets is the one that stays on
        assert entry.enabled == (name == "integrate_google_sheets")
    audit = await container.webhook_audit_repo().list_for_form(workspace.id, setup_.form.form_id)
    assert len(audit) == 3 and {a.event for a in audit} == {"migrated"} and all(a.actor_id is None for a in audit)


async def test_apply_twice_changes_nothing_the_second_time(workspace):
    setup_ = await setup(workspace)
    await tool().apply()
    before = [w.id for w in await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id)]
    again = await tool().apply()
    assert not any(k.startswith("moved.") for k in again.counts)
    assert again.counts["skipped.already_moved"] == 6
    after = [w.id for w in await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id)]
    assert sorted(map(str, before)) == sorted(map(str, after))


async def test_a_submission_after_the_move_is_delivered_once_by_the_new_rows(
    workspace, memory_jobs
):
    setup_ = await setup(workspace)
    await tool().apply()
    await submit(workspace, setup_.form)
    jobs = [(j["queue_name"], j["task_name"]) for j in memory_jobs.jobs.values()]
    assert "actions" not in {queue for queue, _ in jobs}  # nothing for the executor
    # one delivery each: the webhook and Slack (Discord was off), the team copy
    # (a respondent who is not signed in gets none) and the sheet's row
    assert sorted(jobs) == [
        ("emails", "deliver_email"),
        ("integrations", "run_sheets_append"),
        ("webhooks", "deliver_webhook"),
        ("webhooks", "deliver_webhook"),
    ]


async def test_a_run_queued_before_the_move_still_completes_and_one_after_is_not_run_twice(
    workspace, memory_jobs
):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    before = await submit(workspace, setup_.form)
    assert [j["queue_name"] for j in memory_jobs.jobs.values()] == ["actions"]
    await tool().apply()
    after = await submit(workspace, setup_.form)
    service = container.action_service()
    action = setup_.actions["send_webhook"]
    assert await service.run_in_force(workspace.id, setup_.form.form_id, action.id, before.response_id)
    assert not await service.run_in_force(workspace.id, setup_.form.form_id, action.id, after.response_id)


async def test_entry_in_force_boundary():
    import datetime as dt

    now = dt.datetime.now(dt.timezone.utc)
    moved = SimpleNamespace(
        enabled=False, migrated_to={"kind": "webhook", "id": "x", "was_enabled": "true"}, migrated_at=now
    )
    older = SimpleNamespace(created_at=now - dt.timedelta(seconds=5))
    newer = SimpleNamespace(created_at=now + dt.timedelta(seconds=5))
    assert entry_in_force(moved, older) and not entry_in_force(moved, newer)
    off_before = SimpleNamespace(enabled=False, migrated_to={**moved.migrated_to, "was_enabled": "false"}, migrated_at=now)
    assert not entry_in_force(off_before, older)
    sheets_entry = SimpleNamespace(enabled=False, migrated_to={"kind": "sheets"}, migrated_at=now)
    assert not entry_in_force(sheets_entry, older)
    assert entry_in_force(SimpleNamespace(enabled=True, migrated_to=None, migrated_at=None), newer)


async def test_a_form_with_runs_still_queued_is_refused_and_one_that_drains_is_moved(
    workspace, monkeypatch
):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    migration = tool()
    queued = {"n": 1}

    async def count(form_id):
        return queued["n"]

    monkeypatch.setattr(migration, "_queued_runs", count)
    report = await migration.apply()
    assert report.counts["blocked.queued_runs"] == 1
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []

    async def poll(seconds):
        queued["n"] = 0  # the run finished while waiting

    report = await migration.apply(wait_queue_seconds=10, poll=poll)
    assert report.counts["moved.send_webhook"] == 1


async def test_a_fault_while_writing_leaves_the_form_as_it_was(workspace, monkeypatch):
    setup_ = await setup(workspace, FULL[:5])
    migration = tool()

    async def boom(self, item, tid):
        raise RuntimeError("fault")

    monkeypatch.setattr(migrate.BuiltinMigration, "_email_document", boom)
    with pytest.raises(RuntimeError):
        await migration.apply()
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []
    assert await container.form_email_action_repo().list_for_form(workspace.id, setup_.form.form_id) == []
    entries = await entries_of(setup_.form)
    assert all(not e.migrated_to for e in entries.values())
    assert [e.enabled for e in entries.values()] == [True, True, False, True, True]


async def test_a_form_that_changed_since_it_was_planned_is_not_written(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    migration = tool()
    items = await migration.plan_form(setup_.form.form_id)
    document = await container.form_repo().get_form_document_by_id(setup_.form.form_id)
    document.actions[Trigger.on_submit][0].enabled = False  # the creator switched it off meanwhile
    await container.form_repo().save_form(document)
    assert await migration._apply_form(setup_.form.form_id, [i for i in items if i.movable]) is None
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []


# ------------------------------------------------------- verify / rollback


async def test_verify_is_clean_after_apply_and_finds_a_missing_target(workspace):
    setup_ = await setup(workspace)
    await tool().apply()
    clean = await tool().verify()
    assert not any(k.startswith("problem.") for k in clean.counts)
    assert clean.counts["checked.webhook"] == 3 and clean.counts["checked.email"] == 2
    (hook, *_rest) = await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id)
    await container.form_webhook_repo().delete(workspace.id, setup_.form.form_id, hook.id)
    broken = await tool().verify()
    assert broken.counts["problem.webhook_missing"] == 1


async def test_rollback_gives_the_old_actions_back_exactly_and_keeps_the_logs(workspace, memory_jobs):
    setup_ = await setup(workspace)
    original = {k: v.enabled for k, v in (await entries_of(setup_.form)).items()}
    await tool().apply()
    await submit(workspace, setup_.form)  # a log row of the new webhooks exists
    rows_before = len(await container.action_log_repo().many())
    report = await tool().rollback()
    assert report.counts["rolled_back.webhook"] == 3 and report.counts["rolled_back.sheets"] == 1
    entries = await entries_of(setup_.form)
    assert {k: v.enabled for k, v in entries.items()} == original
    assert all(not e.migrated_to and e.migrated_at is None for e in entries.values())
    for hook in await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id):
        assert hook.enabled is False
    for mail in await container.form_email_action_repo().list_for_form(workspace.id, setup_.form.form_id):
        assert mail.enabled is False
    assert len(await container.action_log_repo().many()) == rows_before
    # applying again finds the same rows (the ids are derived): none added
    count = len(await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id))
    await tool().apply()
    assert len(await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id)) == count


async def test_actions_of_someone_elses_own_are_never_touched(workspace):
    form = await publish(workspace)
    custom = await container.action_repository().create_global_action(
        ActionDto(name="partner_sync", action_code="x()", type=FormActionType.EXTERNAL.value), testUser
    )
    document = await container.form_repo().get_form_document_by_id(form.form_id)
    document.actions = {Trigger.on_submit: [ActionState(id=custom.id, enabled=True)]}
    await container.form_repo().save_form(document)
    report = await tool().apply()
    assert report.counts == {}
    assert (await entries_of(form))[str(custom.id)].enabled is True


# --------------------------------------------------------------------- CLI


async def test_the_command_exit_codes():
    parser = migrate_builtins.build_parser()

    class Fake:
        def __init__(self, blocked=0):
            self.report = migrate.Report({"blocked.x": blocked} if blocked else {"ok": 1})

        async def preflight(self, workspace=None):
            return self.report

        async def apply(self, workspace=None, wait_queue_seconds=0):
            return self.report

        async def verify(self, workspace=None):
            return migrate.Report({"problem.both_on": 1})

        async def rollback(self, workspace=None):
            return self.report

    run = migrate_builtins.run
    assert await run(parser.parse_args(["preflight"]), Fake(), temporal=False) == 0
    assert await run(parser.parse_args(["preflight"]), Fake(2), temporal=False) == 1
    assert await run(parser.parse_args(["verify"]), Fake(), temporal=False) == 1
    assert await run(parser.parse_args(["apply"]), Fake(), temporal=False) == 0
    assert parser.parse_args(["apply", "--temporal-drained"]).temporal_drained is True
    assert parser.parse_args(["preflight", "--temporal-drained"]).temporal_drained is True
    with pytest.raises(SystemExit):
        parser.parse_args(["destroy"])


# ----------------------------------------------------------------- Temporal


class FakeTemporal:
    """The Temporal server's list of open ``run_action_code`` workflows."""

    def __init__(self, open_ids=(), reachable=True):
        self.open_ids = list(open_ids)
        self.reachable = reachable
        self.asked = []

    async def __call__(self, form_id):
        self.asked.append(form_id)
        if not self.reachable:
            raise ConnectionError("no temporal")
        return [i for i in self.open_ids if form_id is None or str(form_id) in i]


def temporal_tool(fake, override=False):
    migration = migrate_builtins.migration_of(container, temporal=False, override=override)
    migration._temporal_open_runs = fake
    return migration


async def test_on_temporal_a_form_with_open_workflows_is_not_moved(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    other = await setup(workspace, [("send_to_slack", {"Slack Webhook URL": SLACK}, True)])
    action = str(setup_.actions["send_webhook"].id)
    # a run of the first form is open (the id holds the action, form and response)
    fake = FakeTemporal([f"action_{action}{setup_.form.form_id}65b0000000000000000000ff"])
    report = await temporal_tool(fake).apply()
    assert report.counts["blocked.queued_runs"] == 1  # the first form waits
    assert report.counts["moved.send_to_slack"] == 1  # the second one is not held up
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []
    assert len(await container.form_webhook_repo().list_for_form(workspace.id, other.form.form_id)) == 1
    # the workflow finishes while the command waits
    async def finishes(seconds):
        fake.open_ids.clear()

    report = await temporal_tool(fake).apply(wait_queue_seconds=10, poll=finishes)
    assert report.counts["moved.send_webhook"] == 1


async def test_preflight_counts_the_open_workflows_and_stops_when_temporal_cannot_be_asked(workspace):
    await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    fake = FakeTemporal(["action_aaaa" + "b" * 24 + "c" * 24])
    report = await temporal_tool(fake).preflight()
    assert report.counts["open_run_action_workflows"] == 1 and report.blocked() == 0
    down = FakeTemporal(reachable=False)
    report = await temporal_tool(down).preflight()
    assert report.counts["blocked.temporal_unreachable"] == 1 and report.blocked() == 1


async def test_apply_moves_nothing_while_temporal_cannot_be_asked(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    report = await temporal_tool(FakeTemporal(reachable=False)).apply()
    assert report.counts["blocked.temporal_unreachable"] == 1
    assert not any(k.startswith("moved.") for k in report.counts)
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []


async def test_the_override_skips_an_unreachable_temporal_loudly_and_records_it(workspace):
    from loguru import logger

    setup_ = await setup(workspace, FULL[:1] + FULL[5:])
    seen = []
    handler = logger.add(lambda message: seen.append((message.record["level"].name, str(message))), level="DEBUG")
    try:
        report = await temporal_tool(FakeTemporal(reachable=False), override=True).apply()
    finally:
        logger.remove(handler)
    assert report.counts["moved.send_webhook"] == 1
    assert report.counts["temporal_check_skipped_by_operator"] == 1  # in the output summary
    warned = [text for level, text in seen if level == "WARNING" and "--temporal-drained" in text]
    assert warned and "COULD NOT BE ASKED" in warned[0] and "operator's word" in warned[0]
    # and with every moved action: its entry's marker and the webhook's audit row
    for entry in (await entries_of(setup_.form)).values():
        assert entry.migrated_to["temporal_check"] == "skipped_by_operator"
    audit = await container.webhook_audit_repo().list_for_form(workspace.id, setup_.form.form_id)
    assert [a.changed for a in audit] == [["temporal_check_skipped_by_operator"]]
    # a verify and a rollback still understand such an entry
    assert not any(k.startswith("problem.") for k in (await tool().verify()).counts)
    assert (await tool().rollback()).counts["rolled_back.webhook"] == 1


async def test_an_override_that_was_not_needed_leaves_no_mark(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    report = await temporal_tool(FakeTemporal([]), override=True).apply()  # Temporal answered
    assert "temporal_check_skipped_by_operator" not in report.counts
    (entry,) = (await entries_of(setup_.form)).values()
    assert "temporal_check" not in entry.migrated_to


async def test_an_override_does_not_hide_an_open_workflow_temporal_reported(workspace):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    action = str(setup_.actions["send_webhook"].id)
    fake = FakeTemporal([f"action_{action}{setup_.form.form_id}65b0000000000000000000ff"])
    assert (await temporal_tool(fake, override=True).apply()).counts["blocked.queued_runs"] == 1


@pytest.mark.parametrize("failure", [ConnectionError("down"), PermissionError("auth"), TimeoutError()])
async def test_any_failure_to_ask_temporal_fails_closed(workspace, failure):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])

    async def broken(form_id):
        raise failure

    migration = temporal_tool(broken)
    assert (await migration.preflight()).counts["blocked.temporal_unreachable"] == 1
    report = await migration.apply()
    assert report.counts["blocked.temporal_unreachable"] == 1
    assert not any(k.startswith("moved.") for k in report.counts)  # never "zero open"
    assert await container.form_webhook_repo().list_for_form(workspace.id, setup_.form.form_id) == []


async def test_a_temporal_that_does_not_answer_in_time_fails_closed(workspace, monkeypatch):
    import asyncio

    await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    monkeypatch.setattr(migrate, "TEMPORAL_TIMEOUT_SECONDS", 0.05)

    async def hangs(form_id):
        await asyncio.sleep(30)

    report = await temporal_tool(hangs).apply()
    assert report.counts["blocked.temporal_unreachable"] == 1


async def test_the_command_refuses_with_its_own_exit_code_and_a_message(capsys):
    parser = migrate_builtins.build_parser()

    class Down:
        async def preflight(self, workspace=None):
            return migrate.Report({"blocked.temporal_unreachable": 1})

        async def apply(self, workspace=None, wait_queue_seconds=0):
            return migrate.Report({"blocked.temporal_unreachable": 1, "blocked.queued_runs": 2})

    assert await migrate_builtins.run(parser.parse_args(["preflight"]), Down(), temporal=True) == 3
    assert await migrate_builtins.run(parser.parse_args(["apply"]), Down(), temporal=True) == 3
    err = capsys.readouterr().err
    assert "could not be asked" in err and "--temporal-drained" in err


async def test_the_temporal_service_lists_only_open_run_action_workflows_of_the_form(monkeypatch):
    service = container.temporal_service()
    asked = []

    class Workflow:
        def __init__(self, id):
            self.id = id

    class FakeClient:
        def list_workflows(self, query=None):
            asked.append(query)

            async def stream():
                for item in ("action_x_f1_r1", "action_x_f2_r2", "action_y_f1_r3"):
                    yield Workflow(item)

            return stream()

    monkeypatch.setattr(service, "temporal_client", FakeClient())
    assert await service.open_action_workflows() == ["action_x_f1_r1", "action_x_f2_r2", "action_y_f1_r3"]
    assert await service.open_action_workflows("f1") == ["action_x_f1_r1", "action_y_f1_r3"]
    assert 'WorkflowType="run_action_code"' in asked[0] and 'ExecutionStatus="Running"' in asked[0]


# ------------------------------------------- a moved entry cannot come back on


def _state(action, update, trigger=Trigger.on_submit):
    from backend.app.models.dtos.action_dto import ActionUpdateType, UpdateActionInFormDto

    return UpdateActionInFormDto(
        action_id=action.id, update_type=ActionUpdateType(update), trigger=trigger
    )


async def force_on(form, action):
    """The entry switched on behind the service's back (an old client, a row
    edited by hand): the dispatch must not trust ``enabled`` alone."""
    document = await container.form_repo().get_form_document_by_id(form.form_id)
    for entry in document.actions[Trigger.on_submit]:
        if str(entry.id) == str(action.id):
            entry.enabled = True
    await container.form_repo().save_form(document)


async def test_a_moved_entry_that_is_switched_on_again_is_never_run_by_the_executor(
    workspace, memory_jobs
):
    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    action = setup_.actions["send_webhook"]
    before = await submit(workspace, setup_.form)
    memory_jobs.jobs.clear()
    await tool().apply()
    await force_on(setup_.form, action)
    after = await submit(workspace, setup_.form)
    queues = [(j["queue_name"], j["task_name"]) for j in memory_jobs.jobs.values()]
    assert queues == [("webhooks", "deliver_webhook")]  # the new row only: not the executor too
    service = container.action_service()
    # a run queued before the move still completes; one after never does, switched on or not
    assert await service.run_in_force(workspace.id, setup_.form.form_id, action.id, before.response_id)
    assert not await service.run_in_force(workspace.id, setup_.form.form_id, action.id, after.response_id)


async def test_switching_a_moved_action_on_is_refused_and_off_is_fine(workspace):
    from backend.app.exceptions import HTTPException

    setup_ = await setup(workspace, FULL[:1] + FULL[5:])
    hook, sheet = setup_.actions["send_webhook"], setup_.actions["integrate_google_sheets"]
    await tool().apply()
    form_service = container.form_service()
    with pytest.raises(HTTPException) as refused:
        await form_service.update_state_of_action_in_form(setup_.form.form_id, _state(hook, "enable"))
    assert refused.value.status_code == 409
    assert (await entries_of(setup_.form))[str(hook.id)].enabled is False
    # off stays possible, and the Sheets entry (the backend runs it, on) toggles as ever
    await form_service.update_state_of_action_in_form(setup_.form.form_id, _state(hook, "disable"))
    await form_service.update_state_of_action_in_form(setup_.form.form_id, _state(sheet, "disable"))
    assert (await entries_of(setup_.form))[str(sheet.id)].enabled is False
    await form_service.update_state_of_action_in_form(setup_.form.form_id, _state(sheet, "enable"))
    assert (await entries_of(setup_.form))[str(sheet.id)].migrated_to["kind"] == "sheets"


async def test_an_action_that_was_moved_is_not_added_a_second_time(workspace):
    from backend.app.exceptions import HTTPException
    from backend.app.models.dtos.action_dto import AddActionToFormDto

    setup_ = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    action = setup_.actions["send_webhook"]
    await tool().apply()
    with pytest.raises(HTTPException) as refused:
        await container.form_service().add_action_form(
            setup_.form.form_id, AddActionToFormDto(action_id=action.id), ActionDto(name="send_webhook")
        )
    assert refused.value.status_code == 409
    assert len((await entries_of(setup_.form))) == 1


async def test_once_built_in_actions_have_moved_a_new_one_is_not_attached(workspace):
    from backend.app.exceptions import HTTPException
    from backend.app.models.dtos.action_dto import AddActionToFormDto

    old = await setup(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)])
    other = await publish(workspace)
    fresh = await builtin("send_to_slack")
    # nothing moved yet: attaching works as ever
    await container.form_service().add_action_form(
        other.form_id, AddActionToFormDto(action_id=fresh.id), ActionDto(name="send_to_slack")
    )
    await tool().apply()
    third = await publish(workspace)
    with pytest.raises(HTTPException) as refused:
        await container.form_service().add_action_form(
            third.form_id, AddActionToFormDto(action_id=fresh.id), ActionDto(name="send_to_slack")
        )
    assert refused.value.status_code == 409 and "webhook" in str(refused.value.content)
    # a custom action and the Sheets action are still attached normally
    custom = await container.action_repository().create_global_action(
        ActionDto(name="partner_sync", action_code="x()", type=FormActionType.EXTERNAL.value), testUser
    )
    await container.form_service().add_action_form(
        third.form_id, AddActionToFormDto(action_id=custom.id), ActionDto(name="partner_sync")
    )
    assert str(custom.id) in (await entries_of(third))


async def _race(workspace, specs, writer):
    """``writer(form_id)`` is a form service call started while the move holds the
    form's row lock; the move then writes its marks and commits. Returns the form."""
    import asyncio

    from common.records.codec import row_values

    setup_ = await setup(workspace, specs)
    repo = container.form_repo()
    task = None
    async with repo._session() as session, session.begin():
        stored = await repo._locked_draft(session, setup_.form.form_id)
        task = asyncio.create_task(writer(setup_))
        await asyncio.sleep(0.4)  # the writer is under way: a read-then-write one has its copy by now
        for entry in stored.actions[Trigger.on_submit]:
            if str(entry.id) == str(setup_.actions["send_webhook"].id):
                entry.enabled = False
                entry.migrated_to = {"kind": "webhook", "id": "x", "was_enabled": "true"}
        await session.execute(repo._upsert_statement(row_values(stored)))
    await task
    return setup_


async def test_a_toggle_racing_the_move_does_not_write_back_a_stale_form(workspace):
    specs = [("send_webhook", {"Webhook URL": HOOK}, True), ("send_to_slack", {"Slack Webhook URL": SLACK}, True)]

    async def toggle(setup_):
        return await container.form_service().update_state_of_action_in_form(
            setup_.form.form_id, _state(setup_.actions["send_to_slack"], "disable")
        )

    setup_ = await _race(workspace, specs, toggle)
    entries = await entries_of(setup_.form)
    moved = entries[str(setup_.actions["send_webhook"].id)]
    assert moved.migrated_to and moved.enabled is False  # the mark survived
    assert entries[str(setup_.actions["send_to_slack"].id)].enabled is False  # and the toggle was made


async def test_adding_an_action_racing_the_move_keeps_the_mark(workspace):
    from backend.app.models.dtos.action_dto import AddActionToFormDto

    custom = await container.action_repository().create_global_action(
        ActionDto(name="partner_sync", action_code="x()", type=FormActionType.EXTERNAL.value), testUser
    )

    async def add(setup_):
        return await container.form_service().add_action_form(
            setup_.form.form_id, AddActionToFormDto(action_id=custom.id), ActionDto(name="partner_sync")
        )

    setup_ = await _race(workspace, [("send_webhook", {"Webhook URL": HOOK}, True)], add)
    entries = await entries_of(setup_.form)
    assert entries[str(setup_.actions["send_webhook"].id)].migrated_to
    assert str(custom.id) in entries


async def test_removing_an_action_racing_the_move_keeps_the_mark(workspace):
    specs = [("send_webhook", {"Webhook URL": HOOK}, True), ("send_to_slack", {"Slack Webhook URL": SLACK}, True)]

    async def remove(setup_):
        return await container.form_service().remove_action_from_form(
            setup_.form.form_id, setup_.actions["send_to_slack"].id, Trigger.on_submit
        )

    setup_ = await _race(workspace, specs, remove)
    entries = await entries_of(setup_.form)
    assert list(entries) == [str(setup_.actions["send_webhook"].id)]
    assert entries[str(setup_.actions["send_webhook"].id)].migrated_to
