"""Jobs on Postgres: what TemporalService defers when JOBS_BACKEND routes a job
kind to procrastinate, and what the job bodies do when a worker runs them.
Uses procrastinate's in-memory connector — no queue database needed."""

import datetime as dt
from dataclasses import asdict

import pytest
from beanie import PydanticObjectId
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.models.dataclasses.user_tokens import UserTokens
from backend.app.services.temporal_service import TemporalService
from backend.jobs import tasks
from backend.jobs.app import (
    ACTIONS_QUEUE,
    DEFAULT_QUEUE,
    app,
    libpq_url,
    postgres_jobs_enabled,
)
from common.db import load_flags
from common.models.standard_form import StandardFormResponse
from tests.app.controllers.data import formResponse, testUser


@pytest.fixture
def memory_jobs():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


def service(flags_env):
    return TemporalService(
        server_uri="unused:7233",
        namespace="default",
        crypto=container.crypto(),
        flags=load_flags(flags_env),
        jobs=app,
    )


def test_libpq_url_strips_the_sqlalchemy_driver():
    assert (
        libpq_url("postgresql+asyncpg://u:p@h:5432/db") == "postgresql://u:p@h:5432/db"
    )
    assert libpq_url("postgresql://u:p@h/db") == "postgresql://u:p@h/db"


def test_jobs_app_is_opened_only_when_a_job_kind_uses_postgres():
    assert not postgres_jobs_enabled(load_flags({}))
    assert postgres_jobs_enabled(
        load_flags({"JOBS_BACKEND__delete_response": "postgres"})
    )
    assert postgres_jobs_enabled(load_flags({"JOBS_BACKEND": "postgres"}))


async def test_response_deletion_is_scheduled_at_expiration_and_cancellable(
    memory_jobs,
):
    svc = service({"JOBS_BACKEND__delete_response": "postgres"})
    response = StandardFormResponse(
        response_id="r1", expiration="2031-01-02T03:04:05.000Z", answers={}
    )
    await svc.add_scheduled_job_for_deleting_response(response)
    await svc.add_scheduled_job_for_deleting_response(response)  # queueing lock: once
    jobs = list(memory_jobs.jobs.values())
    assert len(jobs) == 1
    job = jobs[0]
    assert job["task_name"] == "delete_response" and job["queue_name"] == DEFAULT_QUEUE
    assert job["args"] == {"response_id": "r1"}
    assert job["scheduled_at"] == dt.datetime(
        2031, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc
    )
    assert job["queueing_lock"] == "delete_response:r1"
    await svc.delete_response_delete_schedule("r1")
    assert [j for j in memory_jobs.jobs.values() if j["status"] == "todo"] == []
    await svc.delete_response_delete_schedule("r1")  # nothing to cancel is fine


async def test_user_deletion_is_deferred_once_with_encrypted_tokens(memory_jobs):
    svc = service({"JOBS_BACKEND__delete_user": "postgres"})
    tokens = UserTokens(access_token="access-token-secret", refresh_token="refresh-token-secret")
    assert await svc.start_user_deletion_workflow(tokens, "u1") == "Job Started"
    assert (
        await svc.start_user_deletion_workflow(tokens, "u1") is None
    )  # already queued
    (job,) = memory_jobs.jobs.values()
    assert job["task_name"] == "delete_user" and job["args"]["user_id"] == "u1"
    assert (
        "access-token-secret" not in job["args"]["encrypted_tokens"]
    )  # travels encrypted, as with Temporal
    assert container.crypto().decrypt(job["args"]["encrypted_tokens"])


async def test_run_action_is_deferred_by_name_to_the_actions_queue(memory_jobs):
    svc = service({"JOBS_BACKEND__run_action": "postgres"})
    params = {
        "action": '{"id": "x"}',
        "form": "{}",
        "response": "{}",
        "user_email": "e",
        "workspace": "{}",
    }
    await tasks.run_action_deferrer(queueing_lock="action_1").defer_async(**params)
    (job,) = memory_jobs.jobs.values()
    assert job["task_name"] == tasks.RUN_ACTION and job["queue_name"] == ACTIONS_QUEUE
    assert job["args"] == params


async def test_temporal_stays_the_default(memory_jobs):
    svc = service({})
    assert not svc._on_postgres("delete_user")
    assert not svc._on_postgres("run_action")


async def test_delete_response_job_deletes_the_response(
    memory_jobs, workspace, workspace_form_response_for_test
):
    response_id = workspace_form_response_for_test["response_id"]
    assert await container.form_response_repo().get_response(response_id) is not None
    svc = service({"JOBS_BACKEND__delete_response": "postgres"})
    await svc.add_scheduled_job_for_deleting_response(
        StandardFormResponse(
            response_id=response_id, expiration="2020-01-01T00:00:00.000Z", answers={}
        )
    )
    await app.run_worker_async(wait=False, install_signal_handlers=False)
    assert await container.form_response_repo().get_response(response_id) is None
    assert [j["status"] for j in memory_jobs.jobs.values()] == ["succeeded"]
