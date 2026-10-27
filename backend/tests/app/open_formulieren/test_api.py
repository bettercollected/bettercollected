"""The import endpoints: the switch, who may use them, what they return and
what they leave behind."""

import hashlib
import io
import json
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.open_formulieren import limits
from backend.config import settings
from tests.app.auth_helpers import access_token
from backend.app.services.form_service import FormService
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.open_formulieren.conftest import (
    archive_with,
    comp,
    fixture_bytes,
    make_zip,
)

pytestmark = pytest.mark.asyncio

ROOT = "/api/v1"
FIXTURE = "all-components.en.zip"


def url(workspace, *tail):
    return "/".join([f"{ROOT}/workspaces/{workspace.id}/open-formulieren-imports", *tail])


async def upload(client, workspace, cookies, data=None, name="export.zip"):
    return await client.post(
        url(workspace),
        cookies=cookies,
        files={"file": (name, fixture_bytes(FIXTURE) if data is None else data, "application/zip")},
    )


def cookies_of(user):
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def make_viewer(workspace):
    """``invited_user`` is a collaborator of the test workspace: make it a
    viewer, who may read forms but not create or edit them."""
    link = await container.workspace_user_repo().find_workspace_user(
        workspace.id, invited_user.id
    )
    link.roles = [WorkspaceRoles.VIEWER]
    await container.workspace_user_repo().save(link)
    return cookies_of(invited_user)


# -------------------------------------------------------------- the switch


async def test_it_is_off_by_default(client, workspace, test_user_cookies):
    assert settings.open_formulieren.IMPORT == "off"
    ids = "6720a0c1e4b0c8a5f1d2e3f4"
    for method, path, kwargs in (
        ("POST", url(workspace), {"files": {"file": ("a.zip", b"x", "application/zip")}}),
        ("GET", url(workspace, ids), {}),
        ("POST", url(workspace, ids, "review"), {"json": {"reviewed": True}}),
    ):
        # signed in or not, member or not: the switch answers first
        for cookies in (test_user_cookies, cookies_of(testUser1), None):
            response = await client.request(method, path, cookies=cookies, **kwargs)
            assert response.status_code == 410, (method, path, response.text)
            assert response.json()["code"] == "open_formulieren_off"


async def test_off_creates_nothing_even_for_a_good_archive(client, workspace, test_user_cookies):
    response = await upload(client, workspace, test_user_cookies)
    assert response.status_code == 410
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []
    imports = await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren")
    assert imports == []


async def test_an_unknown_mode_refuses_to_start():
    from pydantic import ValidationError

    from backend.config.open_formulieren_settings import OpenFormulierenSettings

    assert OpenFormulierenSettings(IMPORT=" On ").IMPORT == "on"
    with pytest.raises(ValidationError):
        OpenFormulierenSettings(IMPORT="readonly")


async def test_the_providers_list_offers_it_only_when_on(client, monkeypatch):
    before = await client.get(f"{ROOT}/providers")
    assert "open_formulieren" not in [p["providerName"] for p in before.json()]
    monkeypatch.setattr(settings.open_formulieren, "IMPORT", "on")
    after = await client.get(f"{ROOT}/providers")
    assert {"providerName": "open_formulieren", "importMode": "on"} in after.json()


# ---------------------------------------------------------------- a success


async def test_an_import_creates_a_draft_and_reports(
    client, workspace, test_user_cookies, import_on
):
    data = fixture_bytes(FIXTURE)
    response = await upload(client, workspace, test_user_cookies, name="my export.zip")
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {
        "id", "formId", "status", "needsReview", "sourceKind", "sourceVersion",
        "fileName", "sizeBytes", "createdAt", "summary", "report",
    }
    assert body["status"] == "completed" and body["needsReview"] is True
    assert (body["sourceKind"], body["sourceVersion"]) == ("open_formulieren", "4.0.6")
    assert (body["fileName"], body["sizeBytes"]) == ("my export.zip", len(data))
    assert body["summary"] == {"pages": 3, "fields": 27, "logicRules": 1, "repeatingGroups": 1, "dropped": 13, "flagged": 1}
    assert set(body["report"]) == {"truncated", "items"} and body["report"]["truncated"] is False
    flagged = [i for i in body["report"]["items"] if i.get("flag")]
    assert [(i["key"], i["flag"], i["severity"]) for i in flagged] == [("bsn", "national_identity_number", "warning")]

    # a draft: stored, never published, in this workspace
    document = await container.form_repo().get_form_document_by_id(body["formId"])
    assert document.title == "Sample: all components"
    assert document.published_at is None if hasattr(document, "published_at") else True
    assert await container.form_repo().get_latest_version_of_form(body["formId"]) is None
    assert [f.type for f in document.fields].count("slide") == 3
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert link.settings.provider == "self"
    assert link.settings.response_expiration == "30" and link.settings.response_expiration_type.value == "days"
    assert (link.settings.needs_review, link.settings.import_source, link.settings.import_id) == (True, "open_formulieren", body["id"])

    # the record holds the report, never the archive
    record = await container.form_import_repo().get(body["id"])
    assert record.source_kind == "open_formulieren" and record.status == ImportStatus.COMPLETED
    assert record.source_key == "" and record.sha256 == hashlib.sha256(data).hexdigest()
    assert record.form_id == body["formId"] and record.created_by == str(
        (await container.workspace_repo().find_by_id(workspace.id)).owner_id
    )

    again = await client.get(url(workspace, body["id"]), cookies=test_user_cookies)
    assert again.status_code == 200 and again.json() == body


async def test_the_flag_reaches_the_form_settings_the_webapp_reads(
    client, workspace, test_user_cookies, import_on
):
    body = (await upload(client, workspace, test_user_cookies)).json()
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        forms = await client.get(f"{ROOT}/workspaces/{workspace.id}/forms", cookies=test_user_cookies)
    assert forms.status_code == 200, forms.text
    entries = forms.json()
    entries = entries if isinstance(entries, list) else entries.get("items", entries)
    found = [f for f in entries if f.get("formId") == body["formId"]]
    assert found and found[0]["settings"]["needsReview"] is True
    assert found[0]["settings"]["importSource"] == "open_formulieren"
    assert found[0]["settings"]["importId"] == body["id"]


async def test_an_import_with_nothing_to_flag_still_starts_as_needing_review(
    client, workspace, test_user_cookies, import_on
):
    data = archive_with([[comp("textfield", "a", "Name")]])
    body = (await upload(client, workspace, test_user_cookies, data)).json()
    assert body["needsReview"] is True
    assert body["summary"]["flagged"] == 0


# ------------------------------------------------------------------ review


async def test_a_review_is_marked_and_unmarked(client, workspace, test_user_cookies, import_on):
    body = (await upload(client, workspace, test_user_cookies)).json()
    path = url(workspace, body["id"], "review")

    done = await client.post(path, json={"reviewed": True}, cookies=test_user_cookies)
    assert done.status_code == 200 and done.json()["needsReview"] is False
    assert done.json()["report"] == body["report"]  # the report is kept
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert link.settings.needs_review is False and link.settings.import_id == body["id"]
    assert (await client.get(url(workspace, body["id"]), cookies=test_user_cookies)).json()["needsReview"] is False

    again = await client.post(path, json={"reviewed": True}, cookies=test_user_cookies)
    assert again.status_code == 200 and again.json()["needsReview"] is False

    back = await client.post(path, json={"reviewed": False}, cookies=test_user_cookies)
    assert back.json()["needsReview"] is True
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert link.settings.needs_review is True


async def test_a_review_needs_a_body(client, workspace, test_user_cookies, import_on):
    body = (await upload(client, workspace, test_user_cookies)).json()
    response = await client.post(url(workspace, body["id"], "review"), json={}, cookies=test_user_cookies)
    assert response.status_code == 422


# ----------------------------------------------------------- who may do it


async def test_another_workspaces_member_is_refused(
    client, workspace, workspace_1, test_user_cookies, test_user_cookies_1, import_on
):
    body = (await upload(client, workspace, test_user_cookies)).json()
    other = test_user_cookies_1  # an owner, of another workspace
    response = await upload(client, workspace, other)
    assert response.status_code == 403
    assert (await client.get(url(workspace, body["id"]), cookies=other)).status_code == 403
    assert (await client.post(url(workspace, body["id"], "review"), json={"reviewed": True}, cookies=other)).status_code == 403
    # nothing was created for the refused upload: only the first import exists
    assert len(await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren")) == 1


async def test_an_import_is_only_readable_through_its_own_workspace(
    client, workspace, workspace_1, test_user_cookies, test_user_cookies_1, import_on
):
    body = (await upload(client, workspace, test_user_cookies)).json()
    # the other workspace's owner asks for it through their own workspace
    for method, tail, kwargs in (("GET", (), {}), ("POST", ("review",), {"json": {"reviewed": True}})):
        response = await client.request(method, url(workspace_1, body["id"], *tail), cookies=test_user_cookies_1, **kwargs)
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "import_not_found"
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert link.settings.needs_review is True


async def test_a_member_without_form_create_is_refused(
    client, workspace, test_user_cookies, import_on
):
    viewer = await make_viewer(workspace)
    response = await upload(client, workspace, viewer)
    assert response.status_code == 403
    assert await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren") == []
    body = (await upload(client, workspace, test_user_cookies)).json()
    assert (await client.get(url(workspace, body["id"]), cookies=viewer)).status_code == 403
    assert (await client.post(url(workspace, body["id"], "review"), json={"reviewed": True}, cookies=viewer)).status_code == 403


async def test_an_editor_may_import_and_read(client, workspace, import_on):
    editor = cookies_of(invited_user)  # a collaborator: an editor
    body = (await upload(client, workspace, editor)).json()
    assert (await client.get(url(workspace, body["id"]), cookies=editor)).status_code == 200


async def test_it_needs_a_signed_in_user(client, workspace, import_on):
    response = await client.post(url(workspace), files={"file": ("a.zip", b"x", "application/zip")})
    assert response.status_code in (401, 403)


async def test_a_respondent_only_session_is_refused(client, workspace, workspace_1, import_on):
    user = testUser1.model_copy(
        update={"session_scope": "respondent", "scope_workspace_id": str(workspace.id)}
    )
    response = await upload(client, workspace, cookies_of(user))
    assert response.status_code == 403
    assert response.json()["code"] == "respondent_session"


# --------------------------------------------------------- other imports


async def test_pdf_imports_and_these_do_not_see_each_other(
    client, workspace, test_user_cookies, import_on
):
    body = (await upload(client, workspace, test_user_cookies)).json()
    pdf = FormImportDocument(
        workspace_id=workspace.id, form_id=None, created_by="u", status=ImportStatus.COMPLETED,
        file_name="a.pdf", content_type="application/pdf", size_bytes=1, sha256="0", source_key="k",
    )
    await container.form_import_repo().save(pdf)

    # a PDF import is not readable here, and this one is not readable there
    assert (await client.get(url(workspace, str(pdf.id)), cookies=test_user_cookies)).status_code == 404
    assert (await client.post(url(workspace, str(pdf.id), "review"), json={"reviewed": True}, cookies=test_user_cookies)).status_code == 404
    pdf_url = f"{ROOT}/workspaces/{workspace.id}/form-imports"
    assert (await client.get(f"{pdf_url}/{body['id']}", cookies=test_user_cookies)).status_code == 404
    listed = await client.get(pdf_url, cookies=test_user_cookies)
    assert [i["id"] for i in listed.json()] == [str(pdf.id)]


async def test_deleting_the_form_deletes_its_import_record(
    client, workspace, test_user_cookies, import_on
):
    body = (await upload(client, workspace, test_user_cookies)).json()
    await container.workspace_form_service().delete_form_from_workspace(
        workspace.id, body["formId"], testUser
    )
    assert await container.form_import_repo().get(body["id"]) is None
    assert (await client.get(url(workspace, body["id"]), cookies=test_user_cookies)).status_code == 404


# ------------------------------------------------------- refused uploads


async def test_a_request_without_the_file_part_is_refused(
    client, workspace, test_user_cookies, import_on
):
    for kwargs in (
        {"data": {"other": "x"}},
        {"files": {"notfile": ("a.zip", b"x", "application/zip")}},
        {"content": b"{}", "headers": {"content-type": "application/json"}},
        {},
    ):
        response = await client.post(url(workspace), cookies=test_user_cookies, **kwargs)
        assert response.status_code == 400, (kwargs, response.text)
        assert response.json()["code"] == "file_missing"


async def test_an_upload_over_the_limit_is_refused_before_it_is_read(
    client, workspace, test_user_cookies, import_on
):
    big = b"0" * (limits.MAX_UPLOAD_BYTES + 200_000)
    response = await upload(client, workspace, test_user_cookies, big)
    assert response.status_code == 413
    assert response.json() == {
        "code": "file_too_large",
        "message": "The file is too large.",
        "maxBytes": limits.MAX_UPLOAD_BYTES,
    }


async def test_an_upload_just_over_the_limit_inside_the_framing_is_still_refused(
    client, workspace, test_user_cookies, import_on
):
    response = await upload(client, workspace, test_user_cookies, b"0" * (limits.MAX_UPLOAD_BYTES + 1))
    assert response.status_code == 413


async def test_an_unknown_length_is_counted_as_it_arrives(
    client, workspace, test_user_cookies, import_on
):
    """No Content-Length (chunked): the body is still capped."""
    boundary = "xBOUNDARYx"
    head = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="a.zip"\r\n\r\n'.encode()
    tail = f"\r\n--{boundary}--\r\n".encode()

    async def chunks():
        yield head
        for _ in range(8):
            yield b"0" * (1024 * 1024)
        yield tail

    response = await client.post(
        url(workspace),
        cookies=test_user_cookies,
        content=chunks(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 413


@pytest.mark.parametrize(
    "data, status, code",
    [
        (b"not a zip", 400, "not_a_zip"),
        (make_zip({"forms.json": []}), 400, "archive_incomplete"),
        (archive_with([[comp("textfield", "a")]], version="4.3.0"), 400, "open_formulieren_version_unsupported"),
        (archive_with([[comp("signature", "a")]]), 422, "no_importable_fields"),
    ],
    ids=["not-a-zip", "incomplete", "unsupported-version", "no-importable-fields"],
)
async def test_a_refused_archive_creates_nothing(
    client, workspace, test_user_cookies, import_on, data, status, code
):
    response = await upload(client, workspace, test_user_cookies, data)
    assert (response.status_code, response.json()["code"]) == (status, code)
    # no form, and no import: only a content-free note of the attempt (it counts
    # against the workspace's daily attempts)
    records = await container.form_import_repo().list_by_workspace(
        workspace.id, kind="open_formulieren", include_failed=True
    )
    assert [(r.status, r.error_code, r.form_id, r.file_name) for r in records] == [("failed", code, None, "")]
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []


async def test_an_unsupported_version_names_itself(client, workspace, test_user_cookies, import_on):
    response = await upload(client, workspace, test_user_cookies, archive_with([[comp("textfield", "a")]], version="4.3.0"))
    body = response.json()
    assert body["version"] == "4.3.0" and body["supported"] == ["3.2", "3.3", "3.4", "3.5", "4.0"]
    assert "4.3.0" in body["message"]


async def test_the_file_name_is_cleaned(client, workspace, test_user_cookies, import_on):
    body = (await upload(client, workspace, test_user_cookies, name="<img src=x>‮ ex.zip")).json()
    assert body["fileName"] == "ex.zip" and "<" not in body["fileName"]


# -------------------------------------------------------- when it fails


async def test_a_failure_after_the_form_exists_takes_the_draft_away(
    client, workspace, test_user_cookies, import_on
):
    service = container.open_formulieren_import_service()
    with patch.object(service._repo, "save", AsyncMock(side_effect=RuntimeError("boom"))):
        response = await client.post(
            url(workspace),
            cookies=test_user_cookies,
            files={"file": ("a.zip", fixture_bytes(FIXTURE), "application/zip")},
        )
    assert response.status_code >= 500
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []
    assert await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren") == []


async def test_form_creation_switched_off_is_honoured(
    client, workspace, test_user_cookies, import_on, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "ENABLE_FORM_CREATION", False)
    assert (await upload(client, workspace, test_user_cookies)).status_code == 404


async def test_two_imports_of_one_archive_make_two_drafts(
    client, workspace, test_user_cookies, import_on
):
    first = (await upload(client, workspace, test_user_cookies)).json()
    second = (await upload(client, workspace, test_user_cookies)).json()
    assert first["formId"] != second["formId"] and first["id"] != second["id"]
    links = await container.workspace_form_repo().list_in_workspace(workspace.id)
    assert len(links) == 2
