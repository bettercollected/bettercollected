"""The flow over the API: upload, mapping, dry run, import, result; roles, the
switch, caps, atomicity, audit, what must not happen."""

import json

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_import import ImportStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.response_import import limits
from backend.config import settings
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_import import helpers
from tests.app.response_import.helpers import (
    csv_bytes,
    get,
    import_all,
    post,
    publish_form,
    run_job,
    service,
    stored_answers,
    upload,
    url,
)

pytestmark = pytest.mark.asyncio

SIMPLE = [
    {"id": "name", "type": "short_text", "title": "Full name", "validations": {"required": True}},
    {"id": "age", "type": "number", "title": "Age", "validations": {"min_value": 0, "max_value": 120}},
    {
        "id": "colour",
        "type": "dropdown",
        "title": "Colour",
        "properties": {"choices": helpers.CHOICES},
    },
]
HEADER = ["Full name", "Age", "Colour"]


async def simple_form(workspace, **kwargs):
    return await publish_form(workspace, SIMPLE, **kwargs)


async def count(workspace, form) -> int:
    return len(await stored_answers(workspace, form))


async def member(workspace, role):
    other = User(id=str(RecordId()), sub=f"{role.value}@example.org".lower())
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=other.id, roles=[role])
    )
    return other


# ------------------------------------------------------------------ the happy path


async def test_upload_suggests_a_mapping_and_lists_the_targets(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    response = await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "36", "Red"], ["Bob", "", "Blue"]]))
    assert response.status_code == 201, response.text
    body = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert body["status"] == "uploaded"
    assert (body["rowCount"], body["columnCount"], body["encoding"], body["separator"]) == (2, 3, "utf-8", ",")
    assert body["headers"] == HEADER
    assert body["mapping"] == {"0": "q:name", "1": "q:age", "2": "q:colour"}
    keys = {t["key"]: t for t in body["targets"]}
    assert keys["q:name"]["status"] == "ok" and keys["responder"]["status"] == "ignored"
    assert keys["submitted_at"]["status"] == "ok"
    # nothing is stored yet
    assert await count(workspace, form) == 0


async def test_a_dry_run_checks_every_row_and_stores_nothing(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "36", "Red"], ["", "5", "Blue"], ["Cy", "200", "Purple"], ["Di", "x", "Red"]])
    first = (await upload(client, workspace, form, data)).json()
    queued = await post(client, workspace, form, first["id"], "/check", {"mapping": first["mapping"]})
    assert queued.status_code == 202, queued.text
    assert queued.json()["status"] == "checking"
    assert await run_job(first["id"]) == "checked"
    body = (await get(client, workspace, form, first["id"])).json()
    assert body["status"] == "checked"
    assert (body["rowsValid"], body["rowsInvalid"]) == (1, 3)
    found = {(p["row"], p["column"], p["code"]) for p in body["problems"]}
    assert found == {(3, None, "required"), (4, 1, "too_large"), (4, 2, "unknown_option"), (5, 1, "invalid_number")} or found >= {
        (3, 0, "required"),
        (5, 1, "invalid_number"),
        (4, 2, "unknown_option"),
    }
    assert body["problemCounts"]["invalid_number"] == 1
    assert await count(workspace, form) == 0
    # the file waits for the import
    assert await container.response_import_repo().count_files(first["id"]) == 1


async def test_the_import_stores_the_rows_through_the_submissions_encryption(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    body = await import_all(client, workspace, form, csv_bytes([HEADER, ["Ada", "36", "Red"], ["Bob", "", "Blue"]]))
    assert body["status"] == "completed" and body["rowsImported"] == 2 and body["errorCode"] is None
    stored = await stored_answers(workspace, form)
    assert sorted(helpers_text(r, "name") for r in stored) == ["Ada", "Bob"]
    # at rest the answers are ciphertext, not JSON
    raw = await container.form_response_repo().export_batch(
        await container.form_response_service().scope(workspace.id, [form.form_id]), None, after_id=None, limit=10
    )
    assert all(isinstance(r.answers, (bytes, str)) and "Ada" not in str(r.answers) for r in raw)
    assert all(r.csv_import_id == body["id"] and r.provider == "self" for r in raw)
    # the upload is gone, with the job
    assert await container.response_import_repo().count_files(body["id"]) == 0
    assert body["headers"] == []


def helpers_text(response, key):
    answer = response.answers[key]
    return answer["text"] if isinstance(answer, dict) else answer.text


async def test_the_submission_time_is_the_files_or_the_import_time(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    header = HEADER + ["Submitted at (UTC, ISO 8601)"]
    data = csv_bytes([header, ["Ada", "1", "Red", "2026-10-01T10:00:00Z"], ["Bob", "2", "Red", ""]])
    body = await import_all(client, workspace, form, data)
    assert body["status"] == "completed"
    by_name = {helpers_text(r, "name"): r for r in await stored_answers(workspace, form)}
    assert by_name["Ada"].created_at.isoformat().startswith("2026-10-01T10:00:00")
    assert by_name["Bob"].created_at.year == 2026 and by_name["Bob"].created_at > by_name["Ada"].created_at


async def test_the_formula_guard_of_the_export_is_taken_off(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    body = await import_all(client, workspace, form, csv_bytes([HEADER, ["'=SUM(1)", "1", "Red"], ["'+31 6", "2", ""]]))
    assert body["status"] == "completed"
    assert sorted(helpers_text(r, "name") for r in await stored_answers(workspace, form)) == ["+31 6", "=SUM(1)"]


@pytest.mark.parametrize(
    "encoding, separator, bom",
    [("utf-8", ",", False), ("utf-8", ";", True), ("cp1252", ";", False), ("cp1252", ",", False)],
)
async def test_encodings_and_separators(client: AsyncClient, workspace, encoding, separator, bom):
    form = await simple_form(workspace)
    text = csv_bytes([HEADER, ["Zoë Genève", "30", "Red"]], separator=separator).decode("utf-8")
    data = text.encode("utf-8-sig" if bom else encoding)
    body = await import_all(client, workspace, form, data)
    assert body["status"] == "completed", body
    assert helpers_text((await stored_answers(workspace, form))[0], "name") == "Zoë Genève"


async def test_a_decimal_comma_in_a_semicolon_file(client: AsyncClient, workspace):
    form = await publish_form(
        workspace,
        [{"id": "w", "type": "number", "title": "Weight"}, {"id": "n", "type": "short_text", "title": "Name"}],
    )
    body = await import_all(client, workspace, form, csv_bytes([["Weight", "Name"], ["72,5", "Ada"]], separator=";"))
    assert body["status"] == "completed", (body["errorCode"], body["problems"])
    answer = (await stored_answers(workspace, form))[0].answers["w"]
    assert (answer["number"] if isinstance(answer, dict) else answer.number) == 72.5


# ---------------------------------------------------------------------- atomicity


async def test_one_bad_row_stores_nothing_and_says_where(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "36", "Red"], ["Bob", "500", "Red"], ["Cy", "5", "Blue"]])
    body = await import_all(client, workspace, form, data)
    assert body["status"] == "failed" and body["errorCode"] == "validation_failed"
    assert (body["rowsImported"], body["rowsInvalid"], body["rowsValid"]) == (0, 1, 2)
    assert body["problems"] == [{"row": 3, "column": 1, "field": "age", "code": "too_large"}]
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(body["id"]) == 0


async def test_skipping_invalid_rows_imports_the_others(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "36", "Red"], ["Bob", "500", "Red"], ["Cy", "5", "Blue"]])
    body = await import_all(client, workspace, form, data, options={"skipInvalidRows": True})
    assert body["status"] == "completed"
    assert (body["rowsImported"], body["rowsSkipped"]) == (2, 1)
    assert sorted(helpers_text(r, "name") for r in await stored_answers(workspace, form)) == ["Ada", "Cy"]


async def test_a_failure_half_way_deletes_what_was_stored(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    rows = [HEADER] + [[f"Person {i}", "1", "Red"] for i in range(7)]
    repo = container.form_response_repo()
    real = repo.save_form_response
    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 5:
            raise RuntimeError("the database went away")
        return await real(*args, **kwargs)

    monkeypatch.setattr(repo, "save_form_response", flaky)
    body = await import_all(client, workspace, form, csv_bytes(rows))
    assert body["status"] == "failed" and body["errorCode"] == "build_failed"
    assert calls["n"] == 5
    assert await count(workspace, form) == 0
    assert await container.response_import_repo().count_files(body["id"]) == 0


async def test_a_form_limit_is_held_and_a_refused_import_leaves_nothing(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(workspace_id=workspace.id, query=str(form.form_id))
    link.settings.response_limit = 3
    await repo.save_document(link)
    rows = [HEADER] + [[f"P{i}", "1", "Red"] for i in range(5)]
    body = await import_all(client, workspace, form, csv_bytes(rows))
    assert body["status"] == "failed" and body["errorCode"] == "form_full"
    assert await count(workspace, form) == 0
    # within the limit the same import is stored
    ok = await import_all(client, workspace, form, csv_bytes(rows[:3]))
    assert ok["status"] == "completed" and await count(workspace, form) == 2


# ------------------------------------------------------------------------ mapping


async def test_the_mapping_is_validated(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))).json()

    async def run(mapping, confirmed=True):
        return await post(client, workspace, form, first["id"], "/run", {"mapping": mapping, "confirmedLawfulBasis": confirmed})

    cases = [
        ({"0": "q:name", "1": "q:name"}, "duplicate_target"),
        ({"0": "q:nope"}, "unknown_target"),
        ({"9": "q:name"}, "unknown_column"),
        ({"0": "responder"}, "target_not_importable"),
        ({}, "no_mapping"),
        ({"0": "submitted_at"}, "no_mapping"),
    ]
    for mapping, code in cases:
        refused = await run(mapping)
        assert refused.status_code == 422 and refused.json()["code"] == code, (mapping, refused.text)
    refused = await run({"0": "q:name"}, confirmed=False)
    assert refused.status_code == 422 and refused.json()["code"] == "needs_confirmation"
    assert await count(workspace, form) == 0


async def test_a_column_may_be_left_out_and_an_unmapped_required_question_is_a_problem(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    body = await import_all(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]), mapping={"1": "q:age"})
    assert body["status"] == "failed"
    assert body["problems"] == [{"row": 2, "column": None, "field": "name", "code": "required"}]


# ------------------------------------------------------------------ files refused


@pytest.mark.parametrize(
    "data, status, code",
    [
        (b"PK\x03\x04" + b"\x00" * 40, 415, "unsupported_format"),
        (b"", 422, "empty_file"),
        (b"Full name,Age\r\n", 422, "no_rows"),
        ("Full name\r\nx".encode("utf-16"), 422, "unreadable_encoding"),
    ],
)
async def test_files_that_cannot_be_imported(client: AsyncClient, workspace, data, status, code):
    form = await simple_form(workspace)
    response = await upload(client, workspace, form, data)
    assert (response.status_code, response.json()["code"]) == (status, code)
    assert await container.response_import_repo().list_for_form(workspace.id, form.form_id) == []


async def test_the_caps_are_enforced_before_anything_is_kept(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 200)
    big = await upload(client, workspace, form, b"Full name\r\n" + b"x" * 400)
    assert (big.status_code, big.json()["code"]) == (413, "too_large")
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(limits, "MAX_ROWS", 2)
    many = await upload(client, workspace, form, csv_bytes([["Full name"], ["a"], ["b"], ["c"]]))
    assert (many.status_code, many.json()["code"]) == (413, "too_many_rows")
    assert await container.response_import_repo().list_for_form(workspace.id, form.form_id) == []


async def test_a_body_over_the_cap_is_refused_while_it_is_read(client: AsyncClient, workspace, monkeypatch):
    from backend.app.controllers import response_imports_router as router

    form = await simple_form(workspace)
    monkeypatch.setattr(router, "_READ_LIMIT", 100)
    response = await client.post(
        url(workspace, form),
        content=b"x" * 5000,
        headers={"content-type": "text/csv"},
        cookies=_cookies(testUser),
    )
    assert response.status_code == 413


async def test_a_form_post_is_not_accepted_and_nothing_is_spooled_to_disk(client: AsyncClient, workspace, monkeypatch):
    import tempfile

    form = await simple_form(workspace)
    refused = await client.post(
        url(workspace, form), files={"file": ("a.csv", b"Full name\r\nx")}, cookies=_cookies(testUser)
    )
    assert refused.status_code == 415

    def forbidden(*args, **kwargs):
        raise AssertionError("a temporary file was made")

    monkeypatch.setattr(tempfile, "SpooledTemporaryFile", forbidden)
    monkeypatch.setattr(tempfile, "NamedTemporaryFile", forbidden)
    monkeypatch.setattr(tempfile, "TemporaryFile", forbidden)
    accepted = await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))
    assert accepted.status_code == 201
    first = accepted.json()
    await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})
    assert await run_job(first["id"]) == "completed"


# ---------------------------------------------------------- roles, switch, limits


@pytest.mark.parametrize(
    "role, allowed",
    [
        (WorkspaceRoles.ADMIN, True),
        (WorkspaceRoles.COLLABORATOR, False),
        (WorkspaceRoles.REVIEWER, False),
        (WorkspaceRoles.VIEWER, False),
        (WorkspaceRoles.PRIVACY_OFFICER, False),
    ],
)
async def test_only_owner_and_admin_may_import(client: AsyncClient, workspace, role, allowed):
    other = await member(workspace, role)
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    response = await upload(client, workspace, form, data, user=other)
    if allowed:
        assert response.status_code == 201, response.text
    else:
        assert response.status_code == 403, response.text
        assert "Ada" not in response.text
        for method, path in (("get", ""), ("get", "/x"), ("delete", "/x")):
            denied = await getattr(client, method)(url(workspace, form, path), cookies=_cookies(other))
            assert denied.status_code == 403
        for tail in ("/check", "/run", "/rollback"):
            assert (await post(client, workspace, form, "x", tail, user=other)).status_code == 403
        assert await container.response_import_repo().list_for_form(workspace.id, form.form_id) == []


async def test_the_owner_may_and_a_stranger_and_the_signed_out_may_not(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    assert (await upload(client, workspace, form, data, user=testUser)).status_code == 201
    assert (await upload(client, workspace, form, data, user=testUser1)).status_code == 403
    nobody = await client.post(url(workspace, form), content=data, headers={"content-type": "text/csv"})
    assert nobody.status_code in (401, 403)


async def test_an_import_of_another_workspaces_form_is_not_found(client: AsyncClient, workspace, workspace_1):
    mine = await simple_form(workspace)
    first = (await upload(client, workspace, mine, csv_bytes([HEADER, ["Ada", "1", "Red"]]))).json()
    # the same import id through another workspace's route is not theirs
    other_form = await publish_form(workspace_1, SIMPLE, user=testUser1)
    assert (await get(client, workspace_1, other_form, first["id"], user=testUser1)).status_code == 404
    assert (await post(client, workspace, other_form, first["id"], "/run", {"mapping": {"0": "q:name"}, "confirmedLawfulBasis": True})).status_code in (403, 404)


async def test_while_the_switch_is_off_every_route_is_a_404(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))).json()
    monkeypatch.setattr(settings, "CSV_IMPORT_ENABLED", False)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    assert (await upload(client, workspace, form, data)).status_code == 404
    assert (await client.get(url(workspace, form), cookies=_cookies(testUser))).status_code == 404
    assert (await get(client, workspace, form, first["id"])).status_code == 404
    for tail in ("/check", "/run", "/rollback"):
        assert (await post(client, workspace, form, first["id"], tail, {"mapping": first["mapping"]})).status_code == 404
    assert (await client.delete(url(workspace, form, f"/{first['id']}"), cookies=_cookies(testUser))).status_code == 404
    permissions = await client.get(f"/api/v1/workspaces/{workspace.id}/permissions", cookies=_cookies(testUser))
    assert permissions.json()["csvImportEnabled"] is False
    assert "response.import" in permissions.json()["permissions"]
    monkeypatch.setattr(settings, "CSV_IMPORT_ENABLED", True)
    permissions = await client.get(f"/api/v1/workspaces/{workspace.id}/permissions", cookies=_cookies(testUser))
    assert permissions.json()["csvImportEnabled"] is True


async def test_the_sweep_runs_with_the_switch_off(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))).json()
    monkeypatch.setattr(settings, "CSV_IMPORT_ENABLED", False)
    assert await container.response_import_repo().count_files(first["id"]) == 1
    after = limits.FILE_TTL

    from common.clock import utcnow

    later = utcnow() + after + limits.FILE_TTL
    monkeypatch.setattr(service(), "_clock", lambda: later)
    counts = await service().purge_expired()
    assert counts["expired"] == 1
    assert await container.response_import_repo().count_files(first["id"]) == 0


async def test_uploads_are_rate_limited_per_user_and_form(client: AsyncClient, workspace, monkeypatch):
    form = await simple_form(workspace)
    monkeypatch.setattr(limits, "UPLOADS_PER_WINDOW", 2)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    assert (await upload(client, workspace, form, data)).status_code == 201
    assert (await upload(client, workspace, form, data)).status_code == 201
    limited = await upload(client, workspace, form, data)
    assert limited.status_code == 429 and limited.json()["code"] == "rate_limited"
    assert int(limited.headers["retry-after"]) > 0


async def test_one_import_is_run_at_a_time_per_form(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    first = (await upload(client, workspace, form, data)).json()
    body = {"mapping": first["mapping"], "confirmedLawfulBasis": True}
    assert (await post(client, workspace, form, first["id"], "/run", body)).status_code == 202
    again = await post(client, workspace, form, first["id"], "/run", body)
    assert again.status_code == 409 and again.json()["code"] == "import_in_progress"
    second = (await upload(client, workspace, form, data)).json()
    busy = await post(client, workspace, form, second["id"], "/run", {"mapping": second["mapping"], "confirmedLawfulBasis": True})
    assert busy.status_code == 409 and busy.json()["code"] == "import_in_progress"


async def test_a_new_upload_replaces_the_unused_one_of_the_same_person(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    data = csv_bytes([HEADER, ["Ada", "1", "Red"]])
    first = (await upload(client, workspace, form, data)).json()
    second = (await upload(client, workspace, form, data)).json()
    assert await container.response_import_repo().count_files(first["id"]) == 0
    assert await container.response_import_repo().count_files(second["id"]) == 1
    assert (await get(client, workspace, form, first["id"])).json()["status"] == "discarded"


async def test_discard_deletes_the_file(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    first = (await upload(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"]]))).json()
    gone = await client.delete(url(workspace, form, f"/{first['id']}"), cookies=_cookies(testUser))
    assert gone.status_code == 204
    assert await container.response_import_repo().count_files(first["id"]) == 0
    assert (await post(client, workspace, form, first["id"], "/run", {"mapping": first["mapping"], "confirmedLawfulBasis": True})).status_code == 409


# ------------------------------------------------------------------ audit, firing


async def test_the_audit_row_holds_no_content(client: AsyncClient, workspace):
    form = await simple_form(workspace)
    secret = "Zebediah-Ferdinand-Q"
    data = csv_bytes([HEADER, [secret, "36", "Red"], ["Bob", "999", "Red"]])
    body = await import_all(client, workspace, form, data, options={"skipInvalidRows": True})
    assert body["status"] == "completed"
    row = await container.response_import_repo().get_by_id(body["id"])
    stored = json.dumps(row.model_dump(mode="json"))
    for needle in (secret, "Bob", "Full name", "Colour", "999", "Red"):
        assert needle not in stored, needle
    assert row.actor_id == str(testUser.id) and row.file_size > 0
    assert sorted(body["problems"][0]) == ["code", "column", "field", "row"]
    assert "Zebediah" not in json.dumps(body)


async def test_nothing_fires_for_imported_responses(client: AsyncClient, workspace, monkeypatch, memory_jobs):
    form = await simple_form(workspace)
    calls = []

    def spy(owner, name):
        async def record(*args, **kwargs):
            calls.append(name)

        monkeypatch.setattr(owner, name, record)

    spy(container.action_service(), "start_actions_for_submission")
    for service_name, method in (
        ("registration_service", "queue_for_submission"),
        ("webhook_service", "queue_for_submission"),
        ("email_action_service", "queue_for_submission"),
    ):
        spy(getattr(container, service_name)(), method)
    before = len(memory_jobs.jobs)
    body = await import_all(client, workspace, form, csv_bytes([HEADER, ["Ada", "1", "Red"], ["Bob", "2", "Blue"]]))
    assert body["status"] == "completed" and calls == []
    queued = [job["task_name"] for job in list(memory_jobs.jobs.values())[before:]]
    assert queued == ["run_response_import"]
