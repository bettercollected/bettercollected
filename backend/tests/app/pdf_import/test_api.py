"""Uploading a document starts an import that creates a draft form, stores the
original privately with the form, analyses every page in the sandbox, and goes
away with the form."""

import datetime as dt
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.pdf_import.storage import MemoryObjectStore
from tests.app.pdf_import import documents

pytestmark = pytest.mark.asyncio


@pytest.fixture
def store():
    """Object storage in memory; the service and pipeline singletons use it."""
    memory = MemoryObjectStore()
    service, pipeline = container.pdf_import_service(), container.pdf_import_pipeline()
    previous = service._store, pipeline._store
    service._store = pipeline._store = memory
    yield memory
    service._store, pipeline._store = previous


def limits():
    """The settings object the import service actually reads."""
    return container.pdf_import_service()._settings


def url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/form-imports"


async def upload(client, workspace, cookies, data, name="Membership form.pdf"):
    return await client.post(
        url(workspace),
        cookies=cookies,
        files={"file": (name, data, "application/octet-stream")},
    )


async def finished(client, workspace, cookies, import_id):
    await container.pdf_import_service().wait_for_background_imports()
    response = await client.get(f"{url(workspace)}/{import_id}", cookies=cookies)
    assert response.status_code == 200, response.text
    return response.json()


async def test_upload_creates_a_draft_form_and_analyses_every_page(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict,
    store: MemoryObjectStore,
):
    response = await upload(
        client, workspace, test_user_cookies, documents.text_pdf(pages=2)
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert (
        body["status"] == ImportStatus.QUEUED
        and body["contentType"] == "application/pdf"
    )
    assert "sourceKey" not in body and "sha256" not in body

    # the draft form exists right away, titled after the file
    form = await container.form_repo().get_form_document_by_id(body["formId"])
    assert form is not None and form.title == "Membership form"

    # the original is stored privately inside the form's folder
    [key] = store.objects
    assert key.startswith(
        f"private/{workspace.id}/{body['formId']}/imports/{body['id']}/"
    )

    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    assert done["pageCount"] == 2 and [p["route"] for p in done["pages"]] == [
        "text",
        "text",
    ]
    assert done["report"]["routes"] == {"text": 2}

    listed = await client.get(url(workspace), cookies=test_user_cookies)
    assert [i["id"] for i in listed.json()] == [body["id"]]


async def test_each_kind_of_document_gets_its_route(
    client, workspace, test_user_cookies, store
):
    service = container.pdf_import_service()
    previous = limits().CONCURRENT_IMPORTS_PER_WORKSPACE
    limits().CONCURRENT_IMPORTS_PER_WORKSPACE = 10
    try:
        cases = {
            "scan.pdf": (documents.scan_pdf(), ["scan"]),
            "fillable.pdf": (documents.fillable_pdf(), ["widgets"]),
            "photo.png": (documents.photo_png(), ["scan"]),
            "legacy.pdf": (
                documents.text_pdf(["kl/ro kqsf] ljj/0f"], font="Preeti"),
                ["vision"],
            ),
        }
        ids = {}
        for name, (data, _) in cases.items():
            response = await upload(client, workspace, test_user_cookies, data, name)
            assert response.status_code == 202, (name, response.text)
            ids[name] = response.json()["id"]
        await service.wait_for_background_imports()
        for name, (_, expected) in cases.items():
            done = await finished(client, workspace, test_user_cookies, ids[name])
            assert done["status"] == ImportStatus.COMPLETED, (name, done)
            assert [p["route"] for p in done["pages"]] == expected, name
    finally:
        limits().CONCURRENT_IMPORTS_PER_WORKSPACE = previous


async def test_unusable_uploads_are_refused_with_a_reason(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, b"just some text", "notes.txt"
    )
    assert response.status_code == 400 and response.json()["code"] == "unsupported_type"
    assert store.objects == {}

    # a password-protected PDF is accepted as a file, then refused by the analysis
    response = await upload(
        client, workspace, test_user_cookies, documents.encrypted_pdf()
    )
    assert response.status_code == 202
    done = await finished(client, workspace, test_user_cookies, response.json()["id"])
    assert done["status"] == ImportStatus.FAILED
    assert done["report"]["refused"] == "encrypted" and "password" in done["error"]


async def test_limits(client, workspace, test_user_cookies, store):
    repo = container.form_import_repo()
    running = FormImportDocument(
        workspace_id=workspace.id,
        form_id="f-running",
        created_by="u",
        status=ImportStatus.RUNNING,
        file_name="a.pdf",
        content_type="application/pdf",
        size_bytes=1,
        sha256="0" * 64,
        source_key="k",
    )
    await repo.save(running)
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    assert (
        response.status_code == 429 and response.json()["code"] == "import_in_progress"
    )

    running.status = ImportStatus.COMPLETED
    await repo.save(running)
    previous = limits().IMPORTS_PER_WORKSPACE_PER_DAY
    limits().IMPORTS_PER_WORKSPACE_PER_DAY = 1
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        assert response.status_code == 429 and response.json()["code"] == "daily_limit"
    finally:
        limits().IMPORTS_PER_WORKSPACE_PER_DAY = previous


async def test_other_users_cannot_start_or_read_imports(
    client, workspace, test_user_cookies, test_user_cookies_1, store
):
    response = await upload(
        client, workspace, test_user_cookies_1, documents.text_pdf()
    )
    assert response.status_code in (401, 403)
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    import_id = response.json()["id"]
    await container.pdf_import_service().wait_for_background_imports()
    other = await client.get(
        f"{url(workspace)}/{import_id}", cookies=test_user_cookies_1
    )
    assert other.status_code in (401, 403, 404)


async def test_deleting_the_form_deletes_the_import(
    client, workspace, test_user_cookies, store
):
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    body = response.json()
    await container.pdf_import_service().wait_for_background_imports()
    deleted = await client.delete(
        f"/api/v1/workspaces/{workspace.id}/forms/{body['formId']}",
        cookies=test_user_cookies,
    )
    assert deleted.status_code == 200, deleted.text
    assert await container.form_import_repo().get(body["id"]) is None


async def test_a_retried_job_resumes_after_its_last_finished_stage(
    client, workspace, test_user_cookies, store
):
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    import_id = response.json()["id"]
    await container.pdf_import_service().wait_for_background_imports()
    repo = container.form_import_repo()
    record = await repo.get(import_id)
    finished_at = record.stages["analyze"]["finished_at"]
    # simulate a crash after the analysis: the record is running again
    record.status, record.stage = ImportStatus.RUNNING, "next"
    await repo.save(record)
    store.objects.clear()  # the original would only be needed by stages still to run
    rerun = await container.pdf_import_pipeline().run(record.id)
    assert rerun.status == ImportStatus.COMPLETED
    assert rerun.stages["analyze"]["finished_at"] == finished_at
