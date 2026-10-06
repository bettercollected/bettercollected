"""An import whose process died mid-run (e.g. in a deploy) stays "running"
without anyone to finish it. Once it has shown no progress for
``PDF_IMPORT_STALE_AFTER_S`` it is failed as ``interrupted``, so it frees the
workspace's import slot; a healthy import keeps writing a heartbeat and is
never expired (#703). Runs on whichever store is primary."""

import asyncio
import datetime as dt

import pytest

from backend.app.container import container
from backend.app.schemas.form_import import CODE_INTERRUPTED, ImportStatus
from backend.config.pdf_import_settings import PdfImportSettings
from common.models.standard_form import StandardFormField
from tests.app.pdf_import import documents
from tests.app.pdf_import.test_api import (  # noqa: F401 — the store fixture
    _forms_in,
    _gone,
    finished,
    limits,
    store,
    upload,
    url,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def settings_():
    """The service's and the pipeline's settings, put back after the test."""
    s = limits()
    previous = (s.STALE_AFTER_S, s.HEARTBEAT_S)
    yield s
    s.STALE_AFTER_S, s.HEARTBEAT_S = previous


@pytest.fixture
def no_dispatch():
    """Uploads create their import and draft, but no job runs them: the job
    was lost, as when its process is killed."""
    import backend.app.services.pdf_import_service as module

    dispatch = module.PdfImportService._dispatch

    async def nothing(self, import_id):
        return None

    module.PdfImportService._dispatch = nothing
    yield
    module.PdfImportService._dispatch = dispatch


def _ago(seconds):
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)


async def _last_seen(import_id, seconds_ago, status=ImportStatus.RUNNING):
    """Make the import look like its job last showed life ``seconds_ago``."""
    repo = container.form_import_repo()
    record = await repo.get(import_id)
    record.status = status
    record.stage = "structure"
    record.heartbeat_at = record.started_at = record.created_at = _ago(seconds_ago)
    await repo.save(record)
    return record


async def test_a_stale_import_is_expired_on_the_next_start(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    first = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert first.status_code == 202, first.text
    stuck = first.json()
    await _last_seen(stuck["id"], settings_.STALE_AFTER_S + 60)

    second = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert second.status_code == 202, second.text

    expired = await container.form_import_repo().get(stuck["id"])
    assert expired.status == ImportStatus.FAILED
    assert expired.error_code == CODE_INTERRUPTED
    assert expired.report["refused"] == CODE_INTERRUPTED
    assert expired.error == "The import was interrupted. Please try again."
    assert expired.finished_at is not None
    # its empty draft went, like any failed import's
    assert expired.form_id is None and await _gone(stuck["formId"])
    assert stuck["formId"] not in await _forms_in(workspace)
    # the slot is held by the new import only
    assert await container.form_import_repo().count_active(workspace.id) == 1


async def test_an_expired_import_keeps_a_draft_the_user_already_edited(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    stuck = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    forms = container.form_repo()
    draft = await forms.get_form_document_by_id(stuck["formId"])
    draft.fields = [StandardFormField(id="mine", type="short_text", title="Mine")]
    await forms.save_form(draft)
    await _last_seen(stuck["id"], settings_.STALE_AFTER_S + 60)

    second = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert second.status_code == 202, second.text
    expired = await container.form_import_repo().get(stuck["id"])
    assert expired.error_code == CODE_INTERRUPTED
    assert expired.form_id == stuck["formId"]
    kept = await forms.get_form_document_by_id(stuck["formId"])
    assert [f.id for f in kept.fields] == ["mine"]


async def test_a_healthy_import_with_a_fresh_heartbeat_still_holds_the_slot(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    """Long-running is not stale: started hours ago, heartbeat just now."""
    busy = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    record = await _last_seen(busy["id"], 3 * 3600)
    record.heartbeat_at = _ago(1)
    await container.form_import_repo().save(record)

    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert response.status_code == 429
    assert response.json()["code"] == "import_in_progress"
    still = await container.form_import_repo().get(busy["id"])
    assert still.status == ImportStatus.RUNNING and still.form_id == busy["formId"]


async def test_the_threshold_setting_is_respected(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    busy = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    await _last_seen(busy["id"], 300)

    settings_.STALE_AFTER_S = 600  # five minutes of silence is not ten
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert response.status_code == 429

    settings_.STALE_AFTER_S = 120
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert response.status_code == 202, response.text
    expired = await container.form_import_repo().get(busy["id"])
    assert expired.error_code == CODE_INTERRUPTED


async def test_a_queued_import_whose_job_was_lost_is_expired_too(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    lost = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    await _last_seen(lost["id"], settings_.STALE_AFTER_S + 60, ImportStatus.QUEUED)
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert response.status_code == 202, response.text
    expired = await container.form_import_repo().get(lost["id"])
    assert expired.error_code == CODE_INTERRUPTED


async def test_the_progress_screen_learns_the_import_was_interrupted(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    """The screen polls the import: a stale one answers as interrupted
    instead of running forever, without another upload."""
    stuck = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    await _last_seen(stuck["id"], settings_.STALE_AFTER_S + 60)
    response = await client.get(
        f"{url(workspace)}/{stuck['id']}", cookies=test_user_cookies
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == ImportStatus.FAILED
    assert body["errorCode"] == CODE_INTERRUPTED
    assert body["formId"] is None and await _gone(stuck["formId"])


async def test_the_periodic_sweep_expires_stale_imports(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    from backend.jobs import tasks

    stuck = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    await _last_seen(stuck["id"], settings_.STALE_AFTER_S + 60)
    assert await tasks.expire_stale_imports.func(0) != "0 expired"
    expired = await container.form_import_repo().get(stuck["id"])
    assert expired.error_code == CODE_INTERRUPTED
    assert expired.form_id is None and await _gone(stuck["formId"])


def _slow_stage(seconds):
    async def stage(record, data):
        await asyncio.sleep(seconds)
        return {}

    return stage


async def test_a_long_stage_keeps_writing_its_heartbeat_and_is_never_expired(
    client, workspace, test_user_cookies, store, settings_
):
    """A stage longer than the threshold: without the heartbeat the import's
    last save would be older than the threshold mid-stage."""
    settings_.HEARTBEAT_S, settings_.STALE_AFTER_S = 0.05, 0.4
    pipeline = container.pdf_import_pipeline()
    pipeline.stages = lambda: [("structure", _slow_stage(1.5))]
    try:
        body = (
            await upload(client, workspace, test_user_cookies, documents.text_pdf())
        ).json()
        await asyncio.sleep(0.9)  # well past the threshold, inside the stage
        service = container.pdf_import_service()
        assert await service.expire_stale(workspace.id) == 0
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        assert response.status_code == 429
        running = await container.form_import_repo().get(body["id"])
        assert running.status == ImportStatus.RUNNING
        assert running.heartbeat_at is not None
        done = await finished(client, workspace, test_user_cookies, body["id"])
    finally:
        del pipeline.stages
    assert done["status"] == ImportStatus.COMPLETED, done


async def test_an_import_expired_while_running_stops_and_stays_interrupted(
    client, workspace, test_user_cookies, store, settings_
):
    """If a job's heartbeat stalled long enough to be expired, the job stops
    at its next heartbeat instead of writing over the interrupted record."""
    settings_.HEARTBEAT_S = 0.05
    pipeline = container.pdf_import_pipeline()
    pipeline.stages = lambda: [("structure", _slow_stage(30))]
    try:
        body = (
            await upload(client, workspace, test_user_cookies, documents.text_pdf())
        ).json()
        await asyncio.sleep(0.2)
        repo = container.form_import_repo()
        future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        # a heartbeat landing between the read and the write keeps it alive
        # (Mongo checks the heartbeat did not move): try again until it lands
        expired = []
        for _ in range(50):
            expired = await repo.expire_stale(workspace.id, future, _ago(0))
            if expired:
                break
        assert [str(r.id) for r in expired] == [body["id"]]
        await asyncio.wait_for(
            container.pdf_import_service().wait_for_background_imports(), 5
        )
    finally:
        del pipeline.stages
    record = await container.form_import_repo().get(body["id"])
    assert record.status == ImportStatus.FAILED
    assert record.error_code == CODE_INTERRUPTED


async def test_parallel_starts_with_a_stale_import_let_exactly_one_through(
    client, workspace, test_user_cookies, store, no_dispatch, settings_
):
    import backend.app.services.pdf_import_service as module

    stuck = (
        await upload(client, workspace, test_user_cookies, documents.text_pdf())
    ).json()
    await _last_seen(stuck["id"], settings_.STALE_AFTER_S + 60)
    check = module.PdfImportService._check_limits

    async def nothing(self, *args):
        return None

    module.PdfImportService._check_limits = nothing  # every start reaches the insert
    try:
        responses = await asyncio.gather(
            *[
                upload(client, workspace, test_user_cookies, documents.text_pdf())
                for _ in range(4)
            ]
        )
    finally:
        module.PdfImportService._check_limits = check
    assert sorted(r.status_code for r in responses) == [202, 429, 429, 429], [
        r.text for r in responses
    ]
    assert await container.form_import_repo().count_active(workspace.id) == 1
    expired = await container.form_import_repo().get(stuck["id"])
    assert expired.error_code == CODE_INTERRUPTED


async def test_the_threshold_must_outlast_several_heartbeats():
    assert PdfImportSettings().STALE_AFTER_S == 600
    assert PdfImportSettings().HEARTBEAT_S == 30
    PdfImportSettings(STALE_AFTER_S=120, HEARTBEAT_S=30)
    with pytest.raises(ValueError):
        PdfImportSettings(STALE_AFTER_S=60, HEARTBEAT_S=30)
    with pytest.raises(ValueError):
        PdfImportSettings(HEARTBEAT_S=0)
