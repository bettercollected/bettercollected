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


async def test_the_command_exit_codes_and_the_temporal_guard():
    parser = migrate_builtins.build_parser()

    class Fake:
        def __init__(self, blocked=0):
            self.report = migrate.Report({"blocked.x": blocked} if blocked else {"ok": 1})
            self.applied = False

        async def preflight(self, workspace=None):
            return self.report

        async def apply(self, workspace=None, wait_queue_seconds=0):
            self.applied = True
            return self.report

        async def verify(self, workspace=None):
            return migrate.Report({"problem.both_on": 1})

        async def rollback(self, workspace=None):
            return self.report

    run = migrate_builtins.run
    assert await run(parser.parse_args(["preflight"]), Fake(), temporal=False) == 0
    assert await run(parser.parse_args(["preflight"]), Fake(2), temporal=False) == 1
    assert await run(parser.parse_args(["verify"]), Fake(), temporal=False) == 1
    fake = Fake()
    # the executor's queue is Temporal's: the operator has to confirm it is empty
    assert await run(parser.parse_args(["apply"]), fake, temporal=True) == 3 and not fake.applied
    assert await run(parser.parse_args(["apply", "--temporal-drained"]), fake, temporal=True) == 0 and fake.applied
    assert await run(parser.parse_args(["apply"]), Fake(), temporal=False) == 0
    with pytest.raises(SystemExit):
        parser.parse_args(["destroy"])
