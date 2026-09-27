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
                ["text"],
            ),
            "unknown-legacy.pdf": (
                documents.text_pdf(["kl/ro"], font="Kantipur"),
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


async def test_the_text_layer_is_stored_next_to_the_original(
    client, workspace, test_user_cookies, store
):
    data = documents.text_pdf(["kl/ro kqsf] ljj/0f"], font="Preeti")
    response = await upload(client, workspace, test_user_cookies, data, "nepali.pdf")
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    assert done["report"]["text"] == {
        "words": 3,
        "decoded_words": 3,
        "untrusted_words": 0,
    }
    [text_key] = [k for k in store.objects if k.endswith("/text.json")]
    assert text_key.startswith(
        f"private/{workspace.id}/{body['formId']}/imports/{body['id']}/"
    )
    import json

    stored = json.loads(store.objects[text_key])
    assert [w["text"] for w in stored["pages"][0]["words"]] == [
        "परिचय",
        "पत्रको",
        "विवरण",
    ]


async def test_photo_uploads_have_no_text_stage_work(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.photo_png(), "photo.png"
    )
    done = await finished(client, workspace, test_user_cookies, response.json()["id"])
    assert done["status"] == ImportStatus.COMPLETED
    assert not [k for k in store.objects if k.endswith("/text.json")]


async def test_layout_primitives_are_stored_next_to_the_original(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    layout = done["report"]["layout"]
    assert (
        layout["section_bar"] == 2 and layout["cell_run"] == 2 and layout["table"] == 1
    )
    [key] = [k for k in store.objects if k.endswith("/layout.json")]
    import json

    stored = json.loads(store.objects[key])
    kinds = {p["kind"] for p in stored["pages"][0]["primitives"]}
    assert {
        "answer_slot",
        "checkbox",
        "staff_region",
        "photo_box",
        "signature",
    } <= kinds


async def test_an_unreachable_sandbox_fails_the_import_once_retries_are_exhausted(
    client, workspace, test_user_cookies, store
):
    settings_ = limits()
    previous = (settings_.SANDBOX_SOCKET, settings_.CONCURRENT_IMPORTS_PER_WORKSPACE)
    settings_.SANDBOX_SOCKET = "/nonexistent/sandbox.sock"
    settings_.CONCURRENT_IMPORTS_PER_WORKSPACE = 1
    service = container.pdf_import_service()
    import backend.app.services.pdf_import_service as module

    delays = module.RETRY_DELAYS_S
    module.RETRY_DELAYS_S = ()
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        import_id = response.json()["id"]
        await service.wait_for_background_imports()
        given_up = await container.form_import_repo().get(import_id)
        assert given_up.status == ImportStatus.FAILED
        assert "try again later" in given_up.error
        assert given_up.finished_at is not None
        # the failed import no longer holds the workspace's only import slot
        settings_.SANDBOX_SOCKET = previous[0]
        second = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        assert second.status_code == 202, second.text
        done = await finished(client, workspace, test_user_cookies, second.json()["id"])
        assert done["status"] == ImportStatus.COMPLETED, done
    finally:
        settings_.SANDBOX_SOCKET, settings_.CONCURRENT_IMPORTS_PER_WORKSPACE = previous
        module.RETRY_DELAYS_S = delays


async def test_the_import_job_fails_the_import_only_on_its_last_attempt(
    client, workspace, test_user_cookies, store
):
    from types import SimpleNamespace

    import backend.app.services.pdf_import_service as module
    from backend.app.services.pdf_import.sandbox import SandboxUnavailable
    from backend.jobs import tasks

    settings_ = limits()
    previous = settings_.SANDBOX_SOCKET
    dispatch = module.PdfImportService._dispatch

    async def no_dispatch(self, import_id):
        return None

    module.PdfImportService._dispatch = no_dispatch
    settings_.SANDBOX_SOCKET = "/nonexistent/sandbox.sock"
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        import_id = response.json()["id"]
        run = tasks.import_form.func
        first = SimpleNamespace(job=SimpleNamespace(attempts=0))
        with pytest.raises(SandboxUnavailable):
            await run(first, import_id)
        waiting = await container.form_import_repo().get(import_id)
        assert waiting.status == ImportStatus.QUEUED
        last = SimpleNamespace(
            job=SimpleNamespace(attempts=tasks.IMPORT_FORM_ATTEMPTS - 1)
        )
        assert await run(last, import_id) == ImportStatus.FAILED
        failed = await container.form_import_repo().get(import_id)
        assert "try again later" in failed.error
    finally:
        settings_.SANDBOX_SOCKET = previous
        module.PdfImportService._dispatch = dispatch


async def test_the_form_document_model_is_stored_and_summarised(
    client, workspace, test_user_cookies, store, no_real_ai_provider
):
    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    summary = done["report"]["structure"]
    assert summary["pages"] == {"1": "heuristic"} and summary["questions"] >= 5
    assert "isolated document sandbox is not configured" in " ".join(
        done["report"]["notes"]
    )
    import json

    [key] = [k for k in store.objects if k.endswith("/fdm.json")]
    fdm = json.loads(store.objects[key])
    labels = {e["label"] for e in fdm["elements"] if e["type"] == "question"}
    assert {"Full name", "Date of birth", "Account number", "Gender"} <= labels


class CountingProvider:
    """Stands in for the AI provider: counts calls, answers nothing usable."""

    supports_vision = False

    def __init__(self):
        self.calls = 0

    async def analyze_page(self, system, prompt, image, schema):
        self.calls += 1
        return {}


async def _import_with(client, workspace, cookies, no_real_ai_provider, **form):
    provider = CountingProvider()
    no_real_ai_provider._provider_resolver = lambda *_: provider
    response = await client.post(
        url(workspace),
        cookies=cookies,
        files={"file": ("form.pdf", documents.form_pdf(), "application/pdf")},
        data=form,
    )
    assert response.status_code == 202, response.text
    done = await finished(client, workspace, cookies, response.json()["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    return done, provider


async def test_without_consent_nothing_goes_to_the_ai_provider(
    client, workspace, test_user_cookies, store, no_real_ai_provider
):
    from tests.app.ai_helpers import enable_ai

    await enable_ai(workspace)
    for form in ({}, {"ai_consent": "false"}):
        done, provider = await _import_with(
            client, workspace, test_user_cookies, no_real_ai_provider, **form
        )
        assert provider.calls == 0
        assert done["aiConsent"] is False
        assert (
            "AI structuring not used: no consent for this import"
            in done["report"]["notes"]
        )
        record = await container.form_import_repo().get(done["id"])
        assert record.ai_consent is False and record.ai_consent_at is None


async def test_without_the_workspace_opt_in_nothing_goes_to_the_ai_provider(
    client, workspace, test_user_cookies, store, no_real_ai_provider
):
    """The uploader's consent alone is not enough (#715): AI is off for the
    workspace by default, so no provider call and the report says why."""
    done, provider = await _import_with(
        client, workspace, test_user_cookies, no_real_ai_provider, ai_consent="true"
    )
    assert provider.calls == 0
    assert done["aiConsent"] is True
    assert (
        "AI structuring not used: AI is not enabled for this workspace"
        in done["report"]["notes"]
    )
    done, provider = await _import_with(
        client, workspace, test_user_cookies, no_real_ai_provider
    )
    assert provider.calls == 0
    assert (
        "AI structuring not used: AI is not enabled for this workspace; "
        "no consent for this import" in done["report"]["notes"]
    )


async def test_with_both_consents_the_ai_provider_reads_the_pages(
    client, workspace, test_user_cookies, store, no_real_ai_provider
):
    from tests.app.ai_helpers import enable_ai

    await enable_ai(workspace)
    done, provider = await _import_with(
        client, workspace, test_user_cookies, no_real_ai_provider, ai_consent="true"
    )
    assert provider.calls >= 1
    assert done["aiConsent"] is True
    assert not any(
        "AI structuring not used" in note for note in done["report"].get("notes", [])
    )
    record = await container.form_import_repo().get(done["id"])
    assert record.ai_consent is True and record.ai_consent_at is not None
    assert record.ai_consent_by


async def test_the_draft_form_is_filled_from_the_document(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client,
        workspace,
        test_user_cookies,
        documents.form_pdf(),
        "Membership form.pdf",
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    compiled = done["report"]["compile"]
    assert (
        compiled["pages"] >= 1 and compiled["fields"] >= 10 and not compiled["failures"]
    )
    assert compiled["staff_only"][0]["heading"] == "For office use only"
    assert compiled["staff_only"][0]["internal_fields"] == 1
    form = await container.form_repo().get_form_document_by_id(body["formId"])
    titles = [f.title for page in form.fields for f in page.properties.fields]
    assert {"Full name", "Date of birth", "Account number", "Gender"} <= set(titles)
    assert form.theme is not None and form.theme.accent == "#ff0000"


async def test_an_import_makes_staff_parts_internal_and_tables_repeat(
    client, workspace, test_user_cookies, store
):
    from backend.app.services.internal_fields import (
        internal_logic_violations,
        strip_internal_fields,
    )

    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    compiled = done["report"]["compile"]
    assert compiled["internal_fields"] == 1 and compiled["repeating_groups"] == 1
    assert compiled["rules"]["open_table_to_repeating_group"] == 1
    assert not compiled["failures"] and "interim" not in compiled
    form = await container.form_repo().get_form_document_by_id(body["formId"])
    # the staff part: an internal field on the last page, alone
    office = form.fields[-1].properties.fields
    assert [(f.title, f.internal) for f in office] == [("Reviewed by", True)]
    # the table: a repeating group, one question per column, a row per paper row
    [table] = [
        f
        for page in form.fields
        for f in page.properties.fields
        if f.type.value == "group"
    ]
    assert [c.title for c in table.properties.fields] == ["Name", "Relation", "Account"]
    assert table.properties.repeat.max_items == 2
    assert not internal_logic_violations(form)
    # respondents get the form without the staff page
    shown = strip_internal_fields(form.model_copy(deep=True))
    assert len(shown.fields) == len(form.fields) - 1
    assert "Reviewed by" not in [
        f.title for page in shown.fields for f in page.properties.fields
    ]


async def test_compile_never_overwrites_a_draft_the_user_changed(
    client, workspace, test_user_cookies, store
):
    import backend.app.services.pdf_import_service as module
    from common.models.standard_form import StandardFormField

    dispatch = module.PdfImportService._dispatch

    async def no_dispatch(self, import_id):
        return None

    module.PdfImportService._dispatch = no_dispatch
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
        )
    finally:
        module.PdfImportService._dispatch = dispatch
    body = response.json()
    forms = container.form_repo()
    draft = await forms.get_form_document_by_id(body["formId"])
    draft.fields = [StandardFormField(id="mine", type="short_text", title="Mine")]
    await forms.save_form(draft)

    done = await container.pdf_import_pipeline().run(body["id"])
    assert done.status == ImportStatus.COMPLETED
    assert done.report["compile"]["skipped"] == "form was edited"
    kept = await forms.get_form_document_by_id(body["formId"])
    assert [f.id for f in kept.fields] == ["mine"]


async def test_a_retried_compile_gives_the_same_draft(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    forms = container.form_repo()
    first = await forms.get_form_document_by_id(body["formId"])

    # the form was saved but the record was not: the compile stage runs again
    record = await container.form_import_repo().get(body["id"])
    record.stages.pop("compile")
    record.status = ImportStatus.RUNNING
    await container.form_import_repo().save(record)
    again = await container.pdf_import_pipeline().run(record.id)
    assert again.status == ImportStatus.COMPLETED
    assert again.report["compile"].get("note") == "already compiled"
    second = await forms.get_form_document_by_id(body["formId"])
    assert [f.id for f in second.fields] == [f.id for f in first.fields]


async def test_review_data_places_questions_on_their_pages(
    client, workspace, test_user_cookies, test_user_cookies_1, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    await finished(client, workspace, test_user_cookies, body["id"])
    review = await client.get(
        f"{url(workspace)}/{body['id']}/review", cookies=test_user_cookies
    )
    assert review.status_code == 200, review.text
    data = review.json()
    [page] = data["pages"]
    assert page["width"] == 595.0 and page["has_image"] is False
    labels = {b["label"] for b in page["boxes"] if b["type"] == "question"}
    assert {"Full name", "Gender"} <= labels
    full_name = next(b for b in page["boxes"] if b["label"] == "Full name")
    x0, top, x1, bottom = full_name["bbox"]
    assert x0 < 100 and x1 > 400 and 70 < top < 100  # label and box together
    # no image without the isolated sandbox; other users see nothing
    image = await client.get(
        f"{url(workspace)}/{body['id']}/pages/1", cookies=test_user_cookies
    )
    assert image.status_code == 404
    other = await client.get(
        f"{url(workspace)}/{body['id']}/review", cookies=test_user_cookies_1
    )
    assert other.status_code in (401, 403, 404)


async def test_page_images_are_served_privately(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    await finished(client, workspace, test_user_cookies, body["id"])
    record = await container.form_import_repo().get(body["id"])
    key = f"private/x/{body['id']}/pages/1.png"
    store.objects[key] = b"\x89PNG fake"
    record.stages["render"] = {
        "pages": [{"number": 1, "key": key, "width_px": 10, "height_px": 10}]
    }
    await container.form_import_repo().save(record)
    image = await client.get(
        f"{url(workspace)}/{body['id']}/pages/1", cookies=test_user_cookies
    )
    assert image.status_code == 200 and image.content == b"\x89PNG fake"
    assert image.headers["content-type"] == "image/png"
    assert image.headers["cache-control"] == "private, no-store"
    assert image.headers["x-content-type-options"] == "nosniff"


async def test_progress_lists_finished_stages(
    client, workspace, test_user_cookies, store
):
    response = await upload(client, workspace, test_user_cookies, documents.text_pdf())
    done = await finished(client, workspace, test_user_cookies, response.json()["id"])
    assert done["finishedStages"] == [
        "analyze",
        "text",
        "layout",
        "render",
        "structure",
        "compile",
    ]


async def test_the_upload_screen_learns_the_ai_provider_without_sending_anything(
    client, workspace, test_user_cookies, test_user_cookies_1, no_real_ai_provider
):
    from backend.config import settings

    calls = []
    no_real_ai_provider._provider_resolver = lambda *_: calls.append(1)
    previous = (settings.ai.DEFAULT_PROVIDER, settings.open_ai.API_KEY)
    try:
        settings.ai.DEFAULT_PROVIDER, settings.open_ai.API_KEY = "openai", "sk-test"
        info = await client.get(f"{url(workspace)}/ai", cookies=test_user_cookies)
        assert info.status_code == 200, info.text
        assert info.json() == {
            "provider": "OpenAI",
            "available": True,
            "enabled": False,
        }
        from tests.app.ai_helpers import enable_ai

        await enable_ai(workspace)
        info = await client.get(f"{url(workspace)}/ai", cookies=test_user_cookies)
        assert info.json()["enabled"] is True
        settings.open_ai.API_KEY = ""
        info = await client.get(f"{url(workspace)}/ai", cookies=test_user_cookies)
        assert info.json()["available"] is False
        other = await client.get(f"{url(workspace)}/ai", cookies=test_user_cookies_1)
        assert other.status_code in (401, 403, 404)
        assert calls == []
    finally:
        settings.ai.DEFAULT_PROVIDER, settings.open_ai.API_KEY = previous


async def test_review_marks_model_wording_and_tolerates_malformed_elements(
    client, workspace, test_user_cookies, store
):
    import json

    response = await upload(
        client, workspace, test_user_cookies, documents.form_pdf(), "form.pdf"
    )
    body = response.json()
    await finished(client, workspace, test_user_cookies, body["id"])
    [key] = [k for k in store.objects if k.endswith("/fdm.json")]
    fdm = json.loads(store.objects[key])
    question = next(e for e in fdm["elements"] if e.get("type") == "question")
    question["text_source"] = "model"
    fdm["elements"] += ["not an element", {"page": 1}, {"type": "question"}]
    store.objects[key] = json.dumps(fdm).encode()
    review = await client.get(
        f"{url(workspace)}/{body['id']}/review", cookies=test_user_cookies
    )
    assert review.status_code == 200, review.text
    boxes = review.json()["pages"][0]["boxes"]
    marked = [b for b in boxes if b["id"] == question["id"]]
    assert marked and marked[0]["grounded"] is False
    assert any(b["grounded"] for b in boxes)


async def test_answers_on_a_filled_in_form_never_become_questions(
    client, workspace, test_user_cookies, store
):
    import json

    response = await upload(
        client,
        workspace,
        test_user_cookies,
        documents.form_pdf(filled=True),
        "filled.pdf",
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.COMPLETED, done
    [key] = [k for k in store.objects if k.endswith("/fdm.json")]
    fdm = json.dumps(json.loads(store.objects[key]), ensure_ascii=False)
    form = await container.form_repo().get_form_document_by_id(body["formId"])
    titles = [f.title for page in form.fields for f in page.properties.fields]
    compiled = json.dumps([str(t) for t in titles])
    for value in ("Asha", "Kumari", "abroad", "Brother"):
        assert value not in fdm and value not in compiled, value
    assert {"Full name", "Remarks"} <= set(titles)
    # the review screen can say where words were held back
    assert done["report"]["structure"]["withheld_words"].get("1", 0) >= 3


async def _forms_in(workspace):
    return set(
        await container.workspace_form_repo().get_form_ids_in_workspace(workspace.id)
    )


async def _gone(form_id):
    return await container.form_repo().get_form_document_by_id(form_id) is None


async def test_parallel_uploads_cannot_both_pass_the_limits(
    client, workspace, test_user_cookies, store
):
    """The limits hold without the early look: the insert itself is atomic,
    and a refused start takes its draft form away again."""
    import asyncio

    import backend.app.services.pdf_import_service as module

    settings_ = limits()
    previous = (
        settings_.CONCURRENT_IMPORTS_PER_WORKSPACE,
        settings_.IMPORTS_PER_WORKSPACE_PER_DAY,
    )
    service_class = module.PdfImportService
    dispatch, check = service_class._dispatch, service_class._check_limits

    async def nothing(self, *args):
        return None

    # imports stay queued (nothing frees a slot), and every start reaches the insert
    service_class._dispatch = service_class._check_limits = nothing
    before = await _forms_in(workspace)
    try:
        settings_.CONCURRENT_IMPORTS_PER_WORKSPACE = 1
        responses = await asyncio.gather(
            *[
                upload(client, workspace, test_user_cookies, documents.text_pdf())
                for _ in range(4)
            ]
        )
        codes = sorted(r.status_code for r in responses)
        assert codes == [202, 429, 429, 429], [r.text for r in responses]
        refused = {r.json()["code"] for r in responses if r.status_code == 429}
        assert refused == {"import_in_progress"}
        accepted = next(r.json() for r in responses if r.status_code == 202)
        assert await _forms_in(workspace) - before == {accepted["formId"]}

        # the daily limit, with room for parallel imports
        settings_.CONCURRENT_IMPORTS_PER_WORKSPACE = 10
        settings_.IMPORTS_PER_WORKSPACE_PER_DAY = 3
        responses = await asyncio.gather(
            *[
                upload(client, workspace, test_user_cookies, documents.text_pdf())
                for _ in range(5)
            ]
        )
        codes = sorted(r.status_code for r in responses)
        assert codes == [202, 202, 429, 429, 429], [r.text for r in responses]
        refused = {r.json()["code"] for r in responses if r.status_code == 429}
        assert refused == {"daily_limit"}
        assert len(await _forms_in(workspace) - before) == 3
    finally:
        (
            settings_.CONCURRENT_IMPORTS_PER_WORKSPACE,
            settings_.IMPORTS_PER_WORKSPACE_PER_DAY,
        ) = previous
        service_class._dispatch, service_class._check_limits = dispatch, check


async def test_a_refused_document_removes_its_empty_draft(
    client, workspace, test_user_cookies, store
):
    response = await upload(
        client, workspace, test_user_cookies, documents.encrypted_pdf()
    )
    body = response.json()
    done = await finished(client, workspace, test_user_cookies, body["id"])
    assert done["status"] == ImportStatus.FAILED and done["report"]["refused"]
    # the record stays, without its form; the draft and its folder are gone
    assert done["formId"] is None
    assert "The empty draft form was removed" in " ".join(done["report"]["notes"])
    assert await _gone(body["formId"])
    assert body["formId"] not in await _forms_in(workspace)
    review = await client.get(
        f"{url(workspace)}/{body['id']}/review", cookies=test_user_cookies
    )
    assert review.status_code == 404
    listed = await client.get(url(workspace), cookies=test_user_cookies)
    assert body["id"] in {i["id"] for i in listed.json()}


async def test_a_failed_import_removes_its_empty_draft(
    client, workspace, test_user_cookies, store
):
    from backend.app.services.pdf_import.pipeline import MESSAGE_FAILED

    pipeline = container.pdf_import_pipeline()

    async def broken(record, data):
        raise RuntimeError("boom")

    pipeline.stages = lambda: [("analyze", broken)]
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        body = response.json()
        done = await finished(client, workspace, test_user_cookies, body["id"])
    finally:
        del pipeline.stages  # back to the class's stages
    assert done["status"] == ImportStatus.FAILED and done["error"] == MESSAGE_FAILED
    assert done["formId"] is None and await _gone(body["formId"])


async def test_a_failed_import_keeps_a_draft_the_user_already_edited(
    client, workspace, test_user_cookies, store
):
    import backend.app.services.pdf_import_service as module
    from common.models.standard_form import StandardFormField

    dispatch = module.PdfImportService._dispatch

    async def no_dispatch(self, import_id):
        return None

    module.PdfImportService._dispatch = no_dispatch
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.encrypted_pdf()
        )
    finally:
        module.PdfImportService._dispatch = dispatch
    body = response.json()
    forms = container.form_repo()
    draft = await forms.get_form_document_by_id(body["formId"])
    draft.fields = [StandardFormField(id="mine", type="short_text", title="Mine")]
    await forms.save_form(draft)

    done = await container.pdf_import_pipeline().run(body["id"])
    assert done.status == ImportStatus.FAILED
    assert done.form_id == body["formId"]
    kept = await forms.get_form_document_by_id(body["formId"])
    assert [f.id for f in kept.fields] == ["mine"]

    # a published draft counts as touched too
    kept.fields, kept.published_at = [], dt.datetime.now(dt.timezone.utc)
    await forms.save_form(kept)
    done.status = ImportStatus.QUEUED
    await container.form_import_repo().save(done)
    again = await container.pdf_import_pipeline().run(body["id"])
    assert again.status == ImportStatus.FAILED and again.form_id == body["formId"]
    assert not await _gone(body["formId"])


async def test_giving_up_on_the_sandbox_removes_the_empty_draft(
    client, workspace, test_user_cookies, store
):
    import backend.app.services.pdf_import_service as module

    settings_ = limits()
    previous = settings_.SANDBOX_SOCKET
    settings_.SANDBOX_SOCKET = "/nonexistent/sandbox.sock"
    delays = module.RETRY_DELAYS_S
    module.RETRY_DELAYS_S = ()
    try:
        response = await upload(
            client, workspace, test_user_cookies, documents.text_pdf()
        )
        body = response.json()
        done = await finished(client, workspace, test_user_cookies, body["id"])
    finally:
        settings_.SANDBOX_SOCKET = previous
        module.RETRY_DELAYS_S = delays
    assert done["status"] == ImportStatus.FAILED
    assert done["report"]["refused"] == "unavailable"
    assert "try again later" in done["error"]
    assert done["formId"] is None and await _gone(body["formId"])
