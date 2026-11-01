"""Action runs on the Postgres job queue: what is queued (ids only, never
answers, secrets or the responder's address), that the same run is queued once,
that a run which cannot be queued never fails the submission, and what the
backend tells the executor when the job runs (the data, read then, or 410 when
the run no longer applies). Uses procrastinate's in-memory connector."""

import json
import time

import pytest
from common.ids import RecordId
from common.models.standard_form import ActionState, ParameterValue
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.action_run_token import (
    HEADER,
    TTL_SECONDS,
    VALID,
    check_run_token,
    run_token,
)
from backend.config import settings
from backend.app.services import actions_service
from backend.jobs import signals, tasks
from backend.jobs.app import ACTIONS_QUEUE, app
from tests.app.controllers.data import testUser2
from tests.app.services.test_action_secrets import (  # noqa: F401 - fixtures
    CODE,
    CRED,
    HOOK,
    configured_form,
    partner_action,
)

JOB_KEY = "a-generated-job-key"
ANSWER = "THE-ANSWER-42"
RESPONDER = testUser2.sub


@pytest.fixture
def memory_jobs():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


@pytest.fixture(autouse=True)
def job_key(monkeypatch):
    monkeypatch.setattr(settings.temporal_settings, "api_key", JOB_KEY)


async def _submit(workspace, form_id, answer=ANSWER):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form_id,
        StandardFormResponseCamelModel(
            answers={"string": {"type": "text", "text": answer}}, anonymize=False
        ),
        testUser2,
    )


def _context_url(workspace, form, action, response_id):
    return (
        f"/api/v1/temporal/workspaces/{workspace.id}/forms/{form.form_id}"
        f"/actions/{action.id}/runs/{response_id}/context"
    )


def _ask(client, workspace, form, action, response_id, key=JOB_KEY, token=None):
    """The executor's request; the run's own token is the one the backend minted
    for this run unless a test gives another."""
    if token is None:
        token = run_token(workspace.id, form.form_id, action.id, response_id)
    return client.post(
        _context_url(workspace, form, action, response_id),
        headers={"api-key": key, HEADER: token},
    )


def _queued(memory_jobs):
    return [
        job
        for job in memory_jobs.jobs.values()
        if job["task_name"] == tasks.RUN_ACTION
    ]


def _set_status(memory_jobs, job, status):
    memory_jobs.jobs[job["id"]]["status"] = status


async def _submitted(workspace, configured_form, memory_jobs):
    """A submitted run whose job is being run (``doing``), as when the executor
    asks for the run's data."""
    response = await _submit(workspace, configured_form.form_id)
    (job,) = _queued(memory_jobs)
    _set_status(memory_jobs, job, "doing")
    return response, job


class TestWhatIsQueued:
    async def test_a_submission_queues_one_job_of_ids_on_the_actions_queue(
        self, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)

        assert job["queue_name"] == ACTIONS_QUEUE
        args = dict(job["args"])
        token = args.pop("run_token")
        assert args == {
            "action_id": str(partner_action.id),
            "form_id": configured_form.form_id,
            "response_id": response.response_id,
            "workspace_id": str(workspace.id),
        }
        assert check_run_token(
            token,
            workspace.id,
            configured_form.form_id,
            partner_action.id,
            response.response_id,
        ) == VALID

    async def test_no_answer_secret_or_address_is_in_the_job_row(
        self, workspace, configured_form, memory_jobs
    ):
        _, job = await _submitted(workspace, configured_form, memory_jobs)

        row = json.dumps(job, default=str)
        for content in (ANSWER, CRED, HOOK, CODE, "global-secret", RESPONDER):
            assert content not in row

    async def test_the_same_run_is_queued_once(
        self, workspace, configured_form, partner_action, memory_jobs
    ):
        response = await _submit(workspace, configured_form.form_id)
        assert len(_queued(memory_jobs)) == 1
        service = container.temporal_service()
        form = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        stored = await container.form_response_service().workspace_response(
            workspace.id, response.response_id
        )
        workspace_with_action = (
            await container.workspace_repo().get_workspace_with_action_by_id(
                workspace_id=workspace.id, action_id=partner_action.id
            )
        )

        again = await service.start_action_execution(
            partner_action, form, stored, workspace_with_action
        )

        assert again == "already_queued"
        assert len(_queued(memory_jobs)) == 1

    async def test_a_run_that_cannot_be_queued_does_not_fail_the_submission(
        self, workspace, configured_form, memory_jobs, monkeypatch
    ):
        monkeypatch.setattr(actions_service, "QUEUE_RETRY_SECONDS", 0)

        async def broken(**kwargs):
            raise ConnectionError("the queue's database is down")

        class Deferrer:
            defer_async = staticmethod(broken)

        monkeypatch.setattr(tasks, "run_action_deferrer", lambda **kw: Deferrer)
        before = signals.snapshot()["action_runs_not_queued"]

        response = await _submit(workspace, configured_form.form_id)

        assert response is not None and response.submission_uuid
        assert _queued(memory_jobs) == []
        # the loss is visible: counted, and (with its ids) in the error log
        assert signals.snapshot()["action_runs_not_queued"] == before + 1

    async def test_a_failure_that_clears_is_tried_again_and_nothing_is_lost(
        self, workspace, configured_form, memory_jobs, monkeypatch
    ):
        monkeypatch.setattr(actions_service, "QUEUE_RETRY_SECONDS", 0)
        real = tasks.run_action_deferrer
        calls = []

        class Flaky:
            def __init__(self, **kwargs):
                self.inner = real(**kwargs)

            async def defer_async(self, **kwargs):
                calls.append(1)
                if len(calls) == 1:
                    raise ConnectionError("busy")
                return await self.inner.defer_async(**kwargs)

        monkeypatch.setattr(tasks, "run_action_deferrer", Flaky)
        before = signals.snapshot()["action_runs_not_queued"]

        await _submit(workspace, configured_form.form_id)

        assert len(calls) == 2 and len(_queued(memory_jobs)) == 1
        assert signals.snapshot()["action_runs_not_queued"] == before

    async def test_the_error_log_names_the_event_and_ids_never_content(
        self, workspace, configured_form, memory_jobs, monkeypatch
    ):
        from loguru import logger

        monkeypatch.setattr(actions_service, "QUEUE_RETRY_SECONDS", 0)

        async def broken(**kwargs):
            raise ConnectionError(f"down: {ANSWER}")

        class Deferrer:
            defer_async = staticmethod(broken)

        monkeypatch.setattr(tasks, "run_action_deferrer", lambda **kw: Deferrer)
        lines = []
        sink = logger.add(lambda m: lines.append(str(m)), level="ERROR")
        try:
            await _submit(workspace, configured_form.form_id)
        finally:
            logger.remove(sink)
        text = "".join(lines)
        assert "action_run_not_queued" in text and "ConnectionError" in text
        assert ANSWER not in text and RESPONDER not in text


class TestWhatTheExecutorGets:
    async def test_it_gets_the_runs_data_as_it_is_now(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 200, got.text
        body = got.json()
        action_id = str(partner_action.id)
        action = json.loads(body["action"])
        assert action["action_code"] == CODE
        assert action["secrets"][0]["name"] == "Token"
        form = json.loads(body["form"])
        assert form["secrets"][action_id][0]["value"] == CRED
        assert form["parameters"][action_id][0]["value"] == HOOK
        stored = json.loads(body["response"])
        assert stored["answers"]["string"]["text"] == ANSWER  # decrypted for the run
        assert json.loads(body["workspace"])["secrets"][action_id][0]["value"] == CRED
        assert body["user_email"] == RESPONDER

    @pytest.mark.parametrize("key", ["", "wrong"])
    async def test_it_needs_the_job_key(
        self, client, workspace, configured_form, partner_action, memory_jobs, key
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)

        got = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            key=key,
        )

        assert got.status_code == 403
        assert ANSWER not in got.text

    async def test_a_deleted_response_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        await container.form_response_service().delete_response(response.response_id)

        # the executor presents the token the job carries (minted at queue time,
        # in whole seconds): a token minted again here could differ from it when
        # the deletion above takes more than a second, which is a 403, not the
        # 410 under test
        got = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=dict(job["args"])["run_token"],
        )

        assert got.status_code == 410
        assert ANSWER not in got.text

    async def test_an_unknown_response_opens_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        # no job of that run is in flight: refused before anything is looked up
        got = await _ask(
            client, workspace, configured_form, partner_action, str(RecordId())
        )
        assert got.status_code == 403

    async def test_a_switched_off_action_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        form = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        form.actions = {
            "on_submit": [ActionState(id=partner_action.id, enabled=False)]
        }
        await container.form_repo().save_form(form)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 410

    async def test_an_action_taken_off_the_form_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        form = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        form.actions = {"on_submit": []}
        await container.form_repo().save_form(form)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 410

    async def test_a_response_of_another_form_opens_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        other_form = str(RecordId())
        got = await client.post(
            f"/api/v1/temporal/workspaces/{workspace.id}/forms/{other_form}"
            f"/actions/{partner_action.id}/runs/{response.response_id}/context",
            headers={
                "api-key": JOB_KEY,
                HEADER: run_token(
                    workspace.id, other_form, partner_action.id, response.response_id
                ),
            },
        )
        assert got.status_code == 403  # no job of that run is in flight


class TestTheRunsOwnToken:
    """The job key is shared by every internal route; it must not be enough to
    read a response. The token is the backend's, per run."""

    async def test_the_token_in_the_job_opens_that_run_only(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        second = await _submit(workspace, configured_form.form_id, "ANOTHER-ANSWER")
        token = job["args"]["run_token"]

        mine = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=token,
        )
        theirs = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            second.response_id,
            token=token,
        )

        assert mine.status_code == 200, mine.text
        assert theirs.status_code == 403
        assert ANSWER not in theirs.text and "ANOTHER-ANSWER" not in theirs.text

    @pytest.mark.parametrize("token", ["", "0" * 64, "not-a-token"])
    async def test_the_job_key_alone_reads_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs, token
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await client.post(
            _context_url(workspace, configured_form, partner_action, response.response_id),
            headers={"api-key": JOB_KEY, HEADER: token},
        )
        assert got.status_code == 403
        assert ANSWER not in got.text and CRED not in got.text

    async def test_without_any_token_header_it_is_refused(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await client.post(
            _context_url(workspace, configured_form, partner_action, response.response_id),
            headers={"api-key": JOB_KEY},
        )
        assert got.status_code == 403

    async def test_the_token_is_not_made_of_the_ids_or_the_job_key(
        self, workspace, configured_form, partner_action
    ):
        ids = (workspace.id, configured_form.form_id, partner_action.id)
        token = run_token(*ids, "r1")
        expiry, _, signature = token.partition(".")
        assert expiry.isdigit() and len(signature) == 64
        assert signature != run_token(*ids, "r2").partition(".")[2]
        assert JOB_KEY not in token and str(workspace.id) not in token
        assert check_run_token(token, *ids, "r1") == VALID
        assert check_run_token(token, *ids, "r2") != VALID


class TestTheTokenIsBoundToItsJob:
    """The token only opens the run that is in flight: its job is in the actions
    queue, being run, with these ids and this token, and it has not expired."""

    @pytest.mark.parametrize("status", ["todo", "succeeded", "failed", "aborted"])
    async def test_a_job_that_is_not_being_run_opens_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs, status
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        _set_status(memory_jobs, job, status)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 403
        assert ANSWER not in got.text and CRED not in got.text

    async def test_a_valid_token_without_a_job_opens_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        memory_jobs.jobs.pop(job["id"])  # the row is gone (purged, deleted)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 403

    async def test_a_job_with_another_token_or_other_ids_opens_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        stored = memory_jobs.jobs[job["id"]]["args"]
        # the job is for the same lock but another workspace: ids must match exactly
        stored["workspace_id"] = str(RecordId())

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 403

    async def test_an_expired_token_is_skipped_not_run_late(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        old = run_token(
            workspace.id,
            configured_form.form_id,
            partner_action.id,
            response.response_id,
            now=time.time() - 2 * TTL_SECONDS,
        )

        got = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=old,
        )

        assert got.status_code == 410

    async def test_the_expiry_cannot_be_moved(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        _, _, signature = job["args"]["run_token"].partition(".")
        forged = f"{int(time.time()) + 10 * TTL_SECONDS}.{signature}"

        got = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=forged,
        )

        assert got.status_code == 403

    async def test_only_this_actions_settings_are_returned(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        other = str(RecordId())
        form = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        form.secrets = {**form.secrets, other: [ParameterValue(name="Token", value="other-secret")]}
        form.parameters = {
            **form.parameters,
            other: [ParameterValue(name="Webhook URL", value="https://other.example/x")],
        }
        await container.form_repo().save_form(form)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 200, got.text
        assert "other-secret" not in got.text and "other.example" not in got.text
        assert set(json.loads(got.json()["form"])["secrets"]) == {str(partner_action.id)}
