"""Action runs on the Postgres job queue: what is queued (ids only, never
answers, secrets or the responder's address), that the same run is queued once,
that a run which cannot be queued never fails the submission, and what the
backend tells the executor when the job runs (the data, read then, or 410 when
the run no longer applies). Uses procrastinate's in-memory connector."""

import json

import pytest
from common.ids import RecordId
from common.models.standard_form import ActionState
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.config import settings
from backend.jobs import tasks
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


def _ask(client, workspace, form, action, response_id, key=JOB_KEY):
    return client.post(
        _context_url(workspace, form, action, response_id), headers={"api-key": key}
    )


def _queued(memory_jobs):
    return [
        job
        for job in memory_jobs.jobs.values()
        if job["task_name"] == tasks.RUN_ACTION
    ]


async def _submitted(workspace, configured_form, memory_jobs):
    response = await _submit(workspace, configured_form.form_id)
    (job,) = _queued(memory_jobs)
    return response, job


class TestWhatIsQueued:
    async def test_a_submission_queues_one_job_of_ids_on_the_actions_queue(
        self, workspace, configured_form, partner_action, memory_jobs
    ):
        response, job = await _submitted(workspace, configured_form, memory_jobs)

        assert job["queue_name"] == ACTIONS_QUEUE
        assert job["args"] == {
            "action_id": str(partner_action.id),
            "form_id": configured_form.form_id,
            "response_id": response.response_id,
            "workspace_id": str(workspace.id),
        }

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
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
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
        async def broken(**kwargs):
            raise ConnectionError("the queue's database is down")

        class Deferrer:
            defer_async = staticmethod(broken)

        monkeypatch.setattr(tasks, "run_action_deferrer", lambda **kw: Deferrer)

        response = await _submit(workspace, configured_form.form_id)

        assert response is not None and response.submission_uuid
        assert _queued(memory_jobs) == []


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
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        await container.form_response_service().delete_response(response.response_id)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 410
        assert ANSWER not in got.text

    async def test_an_unknown_response_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        got = await _ask(
            client, workspace, configured_form, partner_action, str(RecordId())
        )
        assert got.status_code == 410

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

    async def test_a_response_of_another_form_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        other_form = str(RecordId())
        got = await client.post(
            f"/api/v1/temporal/workspaces/{workspace.id}/forms/{other_form}"
            f"/actions/{partner_action.id}/runs/{response.response_id}/context",
            headers={"api-key": JOB_KEY},
        )
        assert got.status_code == 410


class TestRetention:
    async def test_the_purge_keeps_unfinished_rows_and_clears_old_finished_ones(
        self, memory_jobs
    ):
        # in-memory connector: the call is accepted with the retention windows
        assert tasks.ACTION_JOBS_KEEP_SUCCEEDED_HOURS <= tasks.ACTION_JOBS_KEEP_FAILED_HOURS
        calls = []

        async def delete_old_jobs(**kwargs):
            calls.append(kwargs)

        original = app.job_manager.delete_old_jobs
        app.job_manager.delete_old_jobs = delete_old_jobs
        try:
            assert await tasks.purge_finished_action_jobs.func(0) == "purged"
        finally:
            app.job_manager.delete_old_jobs = original
        assert all(call["queue"] == ACTIONS_QUEUE for call in calls)
        assert {
            call["nb_hours"]: bool(call.get("include_failed")) for call in calls
        } == {
            tasks.ACTION_JOBS_KEEP_SUCCEEDED_HOURS: False,
            tasks.ACTION_JOBS_KEEP_FAILED_HOURS: True,
        }
