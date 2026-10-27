"""Fixes from the independent review: parked retries, re-queueing after a hard
kill, the body's memory budget, the file key, form deletion, the respondent
read and reserved header names."""

import base64
import datetime as dt
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from common.clock import utcnow
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.registration import DeliveryStatus
from backend.app.services.registration import body, client
from backend.config import settings
from backend.jobs.app import app, build_connector
from tests.app.registration.helpers import (
    ANSWERS,
    configure,
    make_service,
    publish,
    submit,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def setup(workspace, registration_on, memory_jobs, tls):
    form = await publish(workspace)
    service = await make_service(workspace)
    await configure(workspace, form, service, ["name"])
    response = await submit(workspace, form)
    (delivery,) = [
        r
        for r in await container.registration_delivery_repo().many()
        if r.response_id == response.response_id
    ]
    return SimpleNamespace(
        workspace=workspace,
        form=form,
        service=service,
        response=response,
        delivery=delivery,
        jobs=memory_jobs,
        tls=tls,
    )


# 1: a retry waiting when the switch goes off is parked as pending, not stranded
async def test_a_retrying_delivery_is_parked_when_the_switch_goes_off(
    setup, monkeypatch
):
    service = container.registration_service()
    setup.tls.script.answers = [(503, {}, b"")]
    await service.run_delivery(str(setup.delivery.id))
    repo = container.registration_delivery_repo()
    assert (await repo.get(setup.delivery.id)).status is DeliveryStatus.RETRYING
    monkeypatch.setattr(settings.registration, "REGISTRATION", "off")
    assert (
        await service.run_delivery(str(setup.delivery.id), job_attempt=1)
    ).status == "skipped"
    parked = await repo.get(setup.delivery.id)
    assert parked.status is DeliveryStatus.PENDING and parked.attempts == 1
    # switched on again: the sweep queues it and it is delivered
    monkeypatch.setattr(settings.registration, "REGISTRATION", "on")
    setup.jobs.jobs.clear()
    later = utcnow() + dt.timedelta(minutes=10)
    service._clock = lambda: later
    try:
        assert (await service.redefer_pending())["queued"] == 1
    finally:
        service._clock = utcnow
    setup.tls.script.answers = [(200, {}, b"{}")]
    assert (await service.run_delivery(str(setup.delivery.id))).status == "delivered"


async def test_the_sweep_also_picks_a_retry_whose_job_vanished(setup):
    service = container.registration_service()
    setup.tls.script.answers = [(503, {}, b"")]
    await service.run_delivery(str(setup.delivery.id))
    setup.jobs.jobs.clear()
    later = utcnow() + dt.timedelta(hours=10)
    service._clock = lambda: later
    try:
        assert (await service.redefer_pending())["rescued"] == 1
    finally:
        service._clock = utcnow
    assert len(setup.jobs.jobs) == 1
    assert (
        await container.registration_delivery_repo().get(setup.delivery.id)
    ).status is DeliveryStatus.PENDING


# 2: no job lock, so a hard-killed worker's `doing` row cannot block the re-queued job
async def test_a_requeued_delivery_runs_while_an_old_doing_job_exists(setup):
    service = container.registration_service()
    job = next(iter(setup.jobs.jobs.values()))
    assert (
        job["lock"] is None
        and job["queueing_lock"] == f"register_submission:{setup.delivery.id}"
    )

    # against the real queue tables: an old job "doing" with the old-style lock
    url = os.environ["DATABASE_URL"]
    connector = build_connector(url)
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
        connect_args={"server_settings": {"search_path": "jobs"}},
    )
    try:
        with app.replace_connector(connector):
            async with app.open_async():
                async with engine.connect() as conn:
                    await conn.execute(text("DELETE FROM jobs.procrastinate_jobs"))
                from backend.jobs import tasks

                await tasks.register_submission.configure(
                    lock=f"register_submission:{setup.delivery.id}"
                ).defer_async(delivery_id=str(setup.delivery.id))
                async with engine.connect() as conn:
                    await conn.execute(
                        text(
                            "UPDATE jobs.procrastinate_jobs SET status = 'doing'::jobs.procrastinate_job_status"
                        )
                    )
                assert await service._queue(setup.delivery) is True
                await app.run_worker_async(
                    queues=["default"], wait=False, install_signal_handlers=False
                )
                async with engine.connect() as conn:
                    rows = (
                        (
                            await conn.execute(
                                text(
                                    "SELECT status FROM jobs.procrastinate_jobs "
                                    "WHERE task_name = 'register_submission' ORDER BY id"
                                )
                            )
                        )
                        .scalars()
                        .all()
                    )
                    await conn.execute(text("DELETE FROM jobs.procrastinate_jobs"))
    finally:
        await engine.dispose()
    assert rows == ["doing", "succeeded"], rows
    assert len(setup.tls.requests) == 1
    assert (
        await container.registration_delivery_repo().get(setup.delivery.id)
    ).status is DeliveryStatus.DELIVERED


# 3: a running size budget while the body is built
def test_the_body_is_built_within_a_file_budget(monkeypatch):
    from common.models.standard_form import StandardForm

    fields = [
        {"id": f"f{i}", "type": "file_upload", "title": f"F{i}"} for i in range(3)
    ]
    form = StandardForm(
        builder_version="v2",
        title="t",
        fields=[{"id": "s", "type": "slide", "properties": {"fields": fields}}],
    )
    monkeypatch.setattr(body, "MAX_FILES_BASE64", 4 * 1024)  # about 3 KB of raw bytes
    seen = []

    def read(file_id, limit=None):
        seen.append((file_id, limit))
        return b"x" * 2000

    answers = {
        f"f{i}": {"type": "file", "file_metadata": {"id": f"id{i}", "name": "a"}}
        for i in range(3)
    }
    with pytest.raises(body.FileTooLarge):
        body.build_values(
            body.variables_of(form),
            [(f"f{i}", f"f{i}") for i in range(3)],
            answers,
            None,
            [],
            read,
        )
    # the second file was only allowed what the first left; the third was never read
    assert [f for f, _ in seen] == ["id0", "id1"]
    assert seen[0][1] == 3072 and seen[1][1] == (4096 - body.base64_size(2000)) * 3 // 4


def test_a_reader_over_its_limit_is_refused_before_loading():
    aws = MagicMock()
    aws.read_object.side_effect = ValueError("object too large")
    reader = container.registration_service().__class__._file_reader(
        SimpleNamespace(_aws=aws), "w", "f", "r"
    )
    with pytest.raises(body.FileTooLarge):
        reader("id1", 100)
    assert aws.read_object.call_args.args == ("private/w/f/r/id1", 100)


# 4: only the response's own folder
async def test_files_are_read_only_from_the_responses_own_folder(setup):
    answers = {
        **ANSWERS,
        "upload": {"type": "file", "file_metadata": {"id": "evil", "name": "x"}},
    }
    form = await publish(setup.workspace)
    await configure(
        setup.workspace,
        form,
        await make_service(setup.workspace, name="Two"),
        ["upload"],
    )
    response = await submit(setup.workspace, form, answers)
    (row,) = [
        r
        for r in await container.registration_delivery_repo().many()
        if r.response_id == response.response_id
    ]
    keys = []

    def read(key, max_bytes):
        keys.append(key)
        return b"leak" if key in ("private/evil", "evil") else None

    with patch.object(container.aws_service(), "read_object", side_effect=read):
        outcome = await container.registration_service().run_delivery(str(row.id))
    assert keys == [
        f"private/{setup.workspace.id}/{form.form_id}/{response.response_id}/evil"
    ]
    assert outcome.status == "failed"
    assert (
        await container.registration_delivery_repo().get(row.id)
    ).last_error_code == "file_missing"
    assert not any(base64.b64encode(b"leak") in r.body for r in setup.tls.requests)


# 5: deleting a form removes its registration and deliveries, whatever the switch says
@pytest.mark.parametrize("switch", ["on", "off"])
async def test_deleting_a_form_removes_its_registration_and_deliveries(
    setup, monkeypatch, switch
):
    monkeypatch.setattr(settings.registration, "REGISTRATION", switch)
    with patch.object(
        container.aws_service(), "delete_folder_from_s3", MagicMock()
    ), patch.object(container.aws_service(), "delete_file_from_s3", MagicMock()):
        await container.workspace_form_service()._delete_form(
            setup.workspace.id, setup.form.form_id
        )
    assert await container.registration_delivery_repo().get(setup.delivery.id) is None
    assert (
        await container.form_registration_repo().get_for_form(
            setup.workspace.id, setup.form.form_id
        )
        is None
    )
    # the service can be deleted again (no 409)
    monkeypatch.setattr(settings.registration, "REGISTRATION", "on")
    from tests.app.controllers.data import testUser

    await container.registration_service().delete_service(
        setup.workspace.id, str(setup.service.id), testUser
    )


async def test_deleting_forms_entirely_removes_their_registration(setup):
    await container.registration_service().delete_for_forms([setup.form.form_id])
    assert await container.registration_delivery_repo().get(setup.delivery.id) is None
    assert (
        await container.form_registration_repo().get_for_form(
            setup.workspace.id, setup.form.form_id
        )
        is None
    )


# 6: the respondent's form load never fails because of registration
async def test_a_registration_failure_never_fails_the_respondents_form(
    client_, setup, monkeypatch
):
    async def boom(*args, **kwargs):
        raise RuntimeError("database trouble")

    monkeypatch.setattr(container.registration_service(), "destination_for", boom)
    response = await client_.get(
        f"/api/v1/workspaces/{setup.workspace.id}/forms/{setup.form.form_id}",
        params={"published": True},
    )
    assert response.status_code == 200
    assert not response.json().get("registrationDestination")


@pytest.fixture()
async def client_(client):
    return client


# 7: header names that steer or frame a request are refused
@pytest.mark.parametrize(
    "name",
    [
        "Host",
        "host",
        "HOST",
        "Content-Length",
        "content-type",
        "Transfer-Encoding",
        "Connection",
        "Keep-Alive",
        "Upgrade",
        "TE",
        "Trailer",
        "Proxy-Authorization",
        "proxy-x",
        "Idempotency-Key",
        "User-Agent",
        "Accept",
        "Accept-Encoding",
        "Cookie",
        "Set-Cookie",
        ":authority",
        "X-Forwarded-Host",
    ],
)
async def test_reserved_header_names_are_refused(workspace, registration_on, tls, name):
    with pytest.raises(HTTPException) as raised:
        await make_service(workspace, auth_name=name)
    assert (
        raised.value.status_code == 422
        and raised.value.content["code"] == "invalid_auth_name"
    )


@pytest.mark.parametrize("name", ["Authorization", "X-Api-Key", "Api-Key", "X-Token"])
async def test_ordinary_header_names_stay_allowed(
    workspace, registration_on, tls, name
):
    created = await make_service(workspace, auth_name=name)
    assert created.auth_name == name


async def test_a_reserved_name_stored_anyway_is_refused_at_send_time(tls):
    target = client.Target(
        base_url="https://case.example.org/",
        auth="header",
        auth_name="Host",
        secret="evil.example.org",
    )
    with pytest.raises(client.SendFailed) as raised:
        await client.post_json(target, b"{}", idempotency_key="d")
    assert raised.value.code == "config_invalid" and tls.requests == []
