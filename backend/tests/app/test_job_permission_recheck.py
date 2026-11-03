"""A background job re-checks the permission of the person who started it, as
that person's ``User`` built from an id and no session. The session-only gates
(the workspace's authenticator-app requirement, single sign-on) were met by the
request that started the job and mean nothing to a job; everything that can
change after it started (membership, role, a disabled workspace, the form's
access) is still decided when the job runs."""

import ast
import pathlib

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_access_grant import ROLE_EDITOR
from backend.app.schemas.response_export import ExportStatus
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.response_export import limits
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import grant, restrict
from tests.app.mfa.helpers import cookies_of_user, member, require_totp
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.response_export.helpers import publish, start, submit_many
from tests.app.response_import.helpers import csv_bytes, import_all, post, run_job, upload
from tests.app.response_import.test_flow import HEADER, simple_form

pytestmark = pytest.mark.asyncio

ROWS = [HEADER, ["Ada", "36", "Red"], ["Bob", "40", "Blue"], ["Cy", "50", "Red"]]


@pytest.fixture(autouse=True)
def switches(monkeypatch, memory_jobs):  # noqa: F811
    """Two responses already make an export job; CSV import is on; jobs queue
    in memory."""
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 2)
    for name in (
        "CSV_IMPORT_ENABLED",
        "NEW_QUESTION_TYPES_ENABLED",
        "ADDRESS_QUESTION_ENABLED",
        "SIGNATURE_QUESTION_ENABLED",
        "FIELD_RULES_ENABLED",
        "CHOICE_LOGIC_ENABLED",
    ):
        monkeypatch.setattr(settings, name, True)
    return memory_jobs


@pytest.fixture(params=["totp_on", "totp_off"])
def totp_mode(request, monkeypatch, workspace):
    """The two worlds a job runs in. With the switch on the workspace requires
    an authenticator app; every requester below presents one."""
    on = request.param == "totp_on"
    monkeypatch.setattr(settings.totp, "ENABLED", on)
    return on


@pytest.fixture()
def totp_on(monkeypatch):
    monkeypatch.setattr(settings.totp, "ENABLED", True)


@pytest.fixture()
def access_on(monkeypatch):
    monkeypatch.setattr(settings.form_access, "ENABLED", True)


async def _arm(totp_mode, workspace):
    """The workspace requires an authenticator app, once its test has set the
    form up (the owner that does so presents none)."""
    if totp_mode:
        await require_totp(workspace)


def _export_job(export_id):
    return container.response_export_service().run_job(export_id)


async def _queued_export(client, workspace, form, user):
    response = await start(client, workspace, form, user=user)
    assert response.status_code == 202, response.text
    return response.json()["id"]


async def _error_code(export_id):
    return (await container.response_export_repo().get_by_id(export_id)).error_code


# ------------------------------------------------------ a job without a session


async def test_an_export_by_an_mfa_verified_requester_completes(
    client: AsyncClient, workspace, totp_on
):
    form = await publish(workspace)
    await submit_many(workspace, form, 4)
    editor = await member(workspace, "exporter@example.org", mfa=True)
    await require_totp(workspace)
    export_id = await _queued_export(client, workspace, form, editor)
    assert await _export_job(export_id) == "ready"
    assert (await container.response_export_repo().get_by_id(export_id)).status == ExportStatus.READY


async def test_an_import_by_an_mfa_verified_confirmer_completes(
    client: AsyncClient, workspace, totp_on
):
    form = await simple_form(workspace)
    admin = await member(workspace, "importer@example.org", WorkspaceRoles.ADMIN, mfa=True)
    await require_totp(workspace)
    done = await import_all(client, workspace, form, csv_bytes(ROWS), user=admin)
    assert done["status"] == "completed" and done["rowsImported"] == 3


async def test_the_owner_with_an_authenticator_app_exports_and_imports(
    client: AsyncClient, workspace, totp_on
):
    owner = testUser.model_copy(update={"mfa": True})
    form = await simple_form(workspace)
    await require_totp(workspace)
    done = await import_all(client, workspace, form, csv_bytes(ROWS), user=owner)
    assert done["status"] == "completed"
    export_id = await _queued_export(client, workspace, form, owner)
    assert await _export_job(export_id) == "ready"


# ------------------------------------------- what changes after the job started


async def test_a_member_removed_mid_export_cancels_it(
    client: AsyncClient, workspace, totp_mode
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    editor = await member(workspace, "gone@example.org", mfa=True)
    await _arm(totp_mode, workspace)
    export_id = await _queued_export(client, workspace, form, editor)
    await container.workspace_user_repo().delete(workspace.id, editor.id)
    assert await _export_job(export_id) == "cancelled"
    assert await _error_code(export_id) == "permission_removed"


async def test_a_member_demoted_mid_export_cancels_it(
    client: AsyncClient, workspace, totp_mode
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    editor = await member(workspace, "demoted@example.org", mfa=True)
    await _arm(totp_mode, workspace)
    export_id = await _queued_export(client, workspace, form, editor)
    repo = container.workspace_user_repo()
    link = await repo.find_workspace_user(workspace.id, RecordId(editor.id))
    link.roles = [WorkspaceRoles.PRIVACY_OFFICER]
    await repo.save_document(link)
    assert await _export_job(export_id) == "cancelled"
    assert await _error_code(export_id) == "permission_removed"


async def test_a_member_disabled_mid_export_cancels_it(
    client: AsyncClient, workspace, totp_mode
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    editor = await member(workspace, "paused@example.org", mfa=True)
    await _arm(totp_mode, workspace)
    export_id = await _queued_export(client, workspace, form, editor)
    repo = container.workspace_user_repo()
    link = await repo.find_workspace_user(workspace.id, RecordId(editor.id))
    link.disabled = True
    await repo.save_document(link)
    assert await _export_job(export_id) == "cancelled"
    assert await _error_code(export_id) == "permission_removed"


async def test_a_member_removed_mid_import_cancels_it(
    client: AsyncClient, workspace, totp_mode
):
    form = await simple_form(workspace)
    admin = await member(workspace, "imp-gone@example.org", WorkspaceRoles.ADMIN, mfa=True)
    await _arm(totp_mode, workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS), user=admin)).json()
    queued = await post(
        client, workspace, form, first["id"], "/run",
        {"mapping": first["mapping"], "confirmedLawfulBasis": True}, user=admin,
    )
    assert queued.status_code == 202, queued.text
    await container.workspace_user_repo().delete(workspace.id, admin.id)
    assert await run_job(first["id"]) == "cancelled"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "permission_removed"


async def test_a_member_demoted_mid_import_cancels_it(
    client: AsyncClient, workspace, totp_mode
):
    form = await simple_form(workspace)
    admin = await member(workspace, "imp-demoted@example.org", WorkspaceRoles.ADMIN, mfa=True)
    await _arm(totp_mode, workspace)
    first = (await upload(client, workspace, form, csv_bytes(ROWS), user=admin)).json()
    queued = await post(
        client, workspace, form, first["id"], "/run",
        {"mapping": first["mapping"], "confirmedLawfulBasis": True}, user=admin,
    )
    assert queued.status_code == 202, queued.text
    repo = container.workspace_user_repo()
    link = await repo.find_workspace_user(workspace.id, RecordId(admin.id))
    link.roles = [WorkspaceRoles.VIEWER]
    await repo.save_document(link)
    assert await run_job(first["id"]) == "cancelled"
    row = await container.response_import_repo().get_by_id(first["id"])
    assert row.error_code == "permission_removed"


async def test_a_form_restricted_mid_export_cancels_it_for_who_lost_access(
    client: AsyncClient, workspace, totp_mode, access_on
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    shut_out = await member(workspace, "shut-out@example.org", mfa=True)
    kept = await member(workspace, "kept@example.org", mfa=True)
    await _arm(totp_mode, workspace)
    first = await _queued_export(client, workspace, form, shut_out)
    second = await _queued_export(client, workspace, form, kept)
    await restrict(workspace, form.form_id)
    await grant(workspace, form.form_id, kept.id, ROLE_EDITOR, export=True)
    assert await _export_job(first) == "cancelled"
    assert await _error_code(first) == "permission_removed"
    assert await _export_job(second) == "ready"


async def test_a_workspace_disabled_mid_export_cancels_it_for_a_member(
    client: AsyncClient, workspace, totp_mode
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    editor = await member(workspace, "ws-off@example.org", mfa=True)
    await _arm(totp_mode, workspace)
    export_id = await _queued_export(client, workspace, form, editor)
    await container.workspace_repo().set_fields(workspace, {"disabled": True})
    assert await _export_job(export_id) == "cancelled"
    assert await _error_code(export_id) == "permission_removed"


# ----------------------------------------------- the request path is unchanged


async def test_a_request_without_the_second_factor_is_still_refused(
    client: AsyncClient, workspace, totp_on
):
    form = await publish(workspace)
    await submit_many(workspace, form, 3)
    import_form = await simple_form(workspace)
    editor = await member(workspace, "no-factor@example.org")
    await require_totp(workspace)
    refused = await start(client, workspace, form, user=editor)
    assert refused.status_code == 403 and refused.json()["code"] == "mfa_required"
    imported = await upload(client, workspace, import_form, csv_bytes(ROWS), user=editor)
    assert imported.status_code == 403


async def test_only_a_job_skips_the_session_gates(workspace, totp_on):
    service = container.authorization_service()
    editor = await member(workspace, "unit@example.org")  # no mfa claim
    await require_totp(workspace)
    export = Permission.RESPONSE_EXPORT
    assert not await service.has_permission(editor, export, workspace.id)
    with pytest.raises(HTTPException) as refused:
        await service.authorize(editor, export, workspace.id)
    assert refused.value.content["code"] == "mfa_required"
    assert await service.has_permission(editor, export, workspace.id, for_job=True)
    # a person who is not a member, or a user without an id, gets nothing either way
    stranger = User(id=str(RecordId()), sub="stranger@example.org")
    assert not await service.has_permission(stranger, export, workspace.id, for_job=True)
    assert not await service.has_permission(None, export, workspace.id, for_job=True)


async def test_a_job_does_not_read_a_missing_sso_claim_as_unmet(workspace, monkeypatch):
    """The single sign-on check is the other session-only gate: asked of a
    request it blocks, asked of a job it is not consulted."""
    service = container.authorization_service()
    editor = await member(workspace, "sso-unit@example.org")

    async def blocks(self, user, ws, is_owner):
        return True

    monkeypatch.setattr(AuthorizationService, "_sso_blocks", blocks)
    export = Permission.RESPONSE_EXPORT
    assert not await service.has_permission(editor, export, workspace.id)
    assert await service.has_permission(editor, export, workspace.id, for_job=True)


async def test_the_invitation_check_does_not_need_the_senders_session(workspace, totp_on):
    """Accepting an invitation re-checks its sender from their id alone."""
    sender = await member(workspace, "sender@example.org", WorkspaceRoles.ADMIN)
    await require_totp(workspace)
    invitation = type("Invitation", (), {"invited_by": sender.id, "role": WorkspaceRoles.EDITOR})()
    await container.workspace_members_service()._refuse_if_inviter_lost_the_role(
        workspace.id, invitation
    )
    await container.workspace_user_repo().delete(workspace.id, sender.id)
    with pytest.raises(HTTPException):
        await container.workspace_members_service()._refuse_if_inviter_lost_the_role(
            workspace.id, invitation
        )


# --------------------------------------------------------------- the call-site guard

SERVICES = pathlib.Path(__file__).resolve().parents[2] / "backend" / "app" / "services"
AUTHORIZING = {"has_permission", "effective_permissions", "authorize", "form_permissions"}


def _functions(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _calls(function, names):
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in names:
                yield node


def _passes_for_job(call) -> bool:
    return any(
        k.arg == "for_job" and isinstance(k.value, ast.Constant) and k.value.value is True
        for k in call.keywords
    )


def test_every_check_of_a_user_built_from_an_id_is_a_job_check():
    unmarked = []
    for path in sorted(SERVICES.rglob("*.py")):
        relative = path.relative_to(SERVICES).as_posix()
        for function in _functions(ast.parse(path.read_text())):
            builds_user = any(True for _ in _calls(function, {"User"}))
            if not builds_user:
                continue
            for call in _calls(function, AUTHORIZING):
                if not _passes_for_job(call):
                    unmarked.append(f"{relative}:{call.lineno} in {function.name}")
    assert not unmarked, (
        "a User built in a function carries no mfa or sso claim: pass for_job=True to the "
        "authorization call it makes: " + ", ".join(unmarked)
    )


@pytest.mark.parametrize(
    "relative, function",
    [
        ("response_export/service.py", "_build"),
        ("response_import/service.py", "_process"),
        ("workspace_members_service.py", "_refuse_if_inviter_lost_the_role"),
    ],
)
def test_the_known_job_rechecks_are_marked(relative, function):
    tree = ast.parse((SERVICES / relative).read_text())
    (node,) = [f for f in _functions(tree) if f.name == function]
    checks = list(_calls(node, AUTHORIZING))
    assert checks and all(_passes_for_job(call) for call in checks)
