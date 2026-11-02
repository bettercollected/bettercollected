"""API key roles and form scope (``API_KEY_ROLES_ENABLED``), the decision only:
a key's permissions on a form are the creator's current ones, narrowed by the
key's role ceiling and, for a key limited to a list of forms, by its row for
the form. It never widens. Everything here is synthetic.

Not here: the routes that set a role or a list (a later change); a key's
limits are written straight to the stored key in these tests."""

import secrets

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
    SUBJECT_KEY,
    FormAccessGrantDocument,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services import api_access
from backend.app.services.ai.api_keys import _hash
from backend.app.services.api_access import (
    acting_user,
    key_permissions_on_form,
    require_key_on_form,
    require_key_scope,
    restrict_to_key_visible,
)
from backend.app.services.api_key_roles import mode
from backend.app.services.api_key_roles.model import (
    SCOPE_ALL,
    SCOPE_LISTED,
    SOURCE_KEY,
    key_decision,
    role_ceiling,
    row_ceiling,
)
from backend.app.services.authorization_service import (
    ADMIN_PERMISSIONS,
    EDITOR_PERMISSIONS,
    PRIVACY_OFFICER_PERMISSIONS,
    REVIEWER_PERMISSIONS,
    VIEWER_PERMISSIONS,
)
from backend.app.services.form_access.model import (
    SOURCE_ROLE,
    FormPermissions,
)
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import SPEC
from tests.app.form_access.helpers import add_member, create_form, grant, restrict
from tests.app.form_access.test_switch_and_memo import statements

P = Permission
BASE = "/api/v1/public/v1"
READ_ALL = ["forms:read", "forms:write", "forms:delete", "responses:read"]
TOKENS = {}


# -- builders -------------------------------------------------------------------------
async def make_key(
    workspace,
    creator,
    scopes=("forms:read", "forms:write", "responses:read"),
    *,
    role=None,
    form_scope=SCOPE_ALL,
    forms=(),
    row_role=ROLE_EDITOR,
) -> WorkspaceAPIKeyDocument:
    """A stored key (as the key routes of a later change will write it), with a
    row for each of ``forms``."""
    token = "bc_" + secrets.token_hex(32)
    document = WorkspaceAPIKeyDocument(
        workspace_id=workspace.id,
        name="a key",
        key_hash=_hash(token),
        prefix=token[:11],
        scopes=list(scopes),
        created_by=str(creator.id),
        responses_read_acknowledged_by=str(creator.id),
        role=role,
        form_scope=form_scope,
    )
    await container.workspace_api_key_repo().save(document)
    TOKENS[str(document.id)] = token  # (the token is never stored)
    for form_id in forms:
        await grant(
            workspace, form_id, document.id, row_role, subject_type=SUBJECT_KEY
        )
    return document


async def admin_creator(workspace, *roles_after):
    """An Admin who then holds ``roles_after`` (nothing: stays Admin)."""
    user = await add_member(workspace, "ADMIN")
    if roles_after:
        await set_roles(workspace, user, *roles_after)
    return user


async def set_roles(workspace, user, *roles):
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, RecordId(user.id))
    membership.roles = list(roles)
    await repo.save(membership)


async def refusal(awaitable):
    with pytest.raises(HTTPException) as error:
        await awaitable
    return error.value.status_code, error.value.content


@pytest.fixture()
def roles_on(monkeypatch):
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", True)


@pytest.fixture()
def roles_off(monkeypatch):
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", False)


# =========================================================================== pure: the tables
def decided(perms, **kw):
    return FormPermissions(frozenset(perms), SOURCE_ROLE, form_found=True, **kw)


def test_no_role_is_no_ceiling_and_an_unknown_role_is_nothing():
    assert role_ceiling(None, ["responses:read"]) is None
    for role in ("OWNER", "ADMIN", "", "SUPERUSER", "owner "):
        assert role_ceiling(role, READ_ALL) == frozenset(), role


def test_a_role_ceiling_is_the_roles_own_permissions():
    assert role_ceiling("EDITOR") == EDITOR_PERMISSIONS
    assert role_ceiling("COLLABORATOR") == EDITOR_PERMISSIONS  # the stored spelling
    assert role_ceiling("REVIEWER") == REVIEWER_PERMISSIONS
    assert role_ceiling("VIEWER") == VIEWER_PERMISSIONS
    assert role_ceiling("PRIVACY_OFFICER") == PRIVACY_OFFICER_PERMISSIONS


def test_a_read_only_role_exports_only_with_the_responses_read_scope():
    for role, base in (("REVIEWER", REVIEWER_PERMISSIONS), ("VIEWER", VIEWER_PERMISSIONS)):
        assert P.RESPONSE_EXPORT not in role_ceiling(role, ["forms:read"])
        carrying = role_ceiling(role, ["forms:read", "responses:read"])
        assert carrying == base | {P.RESPONSE_EXPORT}
    # never the privacy officer: it never reads answers
    assert not role_ceiling("PRIVACY_OFFICER", ["responses:read"]) & {
        P.RESPONSE_READ,
        P.RESPONSE_EXPORT,
    }


def test_no_key_role_holds_a_workspace_permission():
    held = frozenset().union(
        *(role_ceiling(r, READ_ALL) for r in ("EDITOR", "REVIEWER", "VIEWER"))
    )
    assert not held & {P.WORKSPACE_BILLING, P.SECURITY_MANAGE}


def test_a_rows_ceiling_never_deletes_a_form_and_an_unknown_role_allows_nothing():
    assert P.FORM_DELETE in role_ceiling("EDITOR")
    assert P.FORM_DELETE not in row_ceiling(ROLE_EDITOR)
    assert P.FORM_EDIT in row_ceiling(ROLE_EDITOR)
    assert row_ceiling("ADMIN") == frozenset()
    assert row_ceiling("SUPERUSER") == frozenset()
    assert P.RESPONSE_EXPORT not in row_ceiling(ROLE_VIEWER)
    assert P.RESPONSE_EXPORT in row_ceiling(ROLE_VIEWER, ["responses:read"])
    assert P.RESPONSE_EXPORT in row_ceiling(ROLE_EDITOR)


def row(role=ROLE_EDITOR):
    return FormAccessGrantDocument(
        workspace_id=RecordId(),
        form_id="f",
        subject_type=SUBJECT_KEY,
        subject_id="k",
        role=role,
    )


def test_decision_without_limits_is_the_creators_decision_itself():
    creator = decided(ADMIN_PERMISSIONS)
    assert key_decision(creator, ceiling=None, listed=False, row=None) is creator


def test_the_role_ceiling_narrows_and_never_adds():
    creator = decided(ADMIN_PERMISSIONS)
    got = key_decision(
        creator, ceiling=role_ceiling("VIEWER"), listed=False, row=None
    )
    assert got.permissions == VIEWER_PERMISSIONS and got.source == SOURCE_KEY
    # a creator who holds less than the role: the key holds what the creator holds
    weak = decided(VIEWER_PERMISSIONS)
    got = key_decision(weak, ceiling=role_ceiling("EDITOR"), listed=False, row=None)
    assert got.permissions == VIEWER_PERMISSIONS
    assert got is weak  # nothing was narrowed


def test_a_listed_key_without_a_row_is_closed_like_a_missing_form():
    creator = decided(ADMIN_PERMISSIONS)
    got = key_decision(creator, ceiling=None, listed=True, row=None)
    assert got.hidden and not got.permissions


def test_a_row_is_a_ceiling_and_never_an_addition():
    admin = decided(ADMIN_PERMISSIONS)
    got = key_decision(admin, ceiling=None, listed=True, row=row(ROLE_EDITOR))
    assert P.FORM_EDIT in got.permissions and P.FORM_DELETE not in got.permissions
    # the narrower of role and row
    got = key_decision(
        admin, ceiling=role_ceiling("VIEWER"), listed=True, row=row(ROLE_EDITOR)
    )
    assert got.permissions == VIEWER_PERMISSIONS
    got = key_decision(
        admin, ceiling=role_ceiling("EDITOR"), listed=True, row=row(ROLE_VIEWER)
    )
    assert got.permissions == VIEWER_PERMISSIONS
    # a row can not give what the creator lacks
    weak = decided(VIEWER_PERMISSIONS)
    got = key_decision(weak, ceiling=None, listed=True, row=row(ROLE_EDITOR))
    assert got.permissions == VIEWER_PERMISSIONS
    # a row with a role this code does not know allows nothing
    got = key_decision(admin, ceiling=None, listed=True, row=row("SUPERUSER"))
    assert got.permissions == frozenset() and not got.hidden


def test_a_creator_with_nothing_or_a_closed_form_stays_that_way():
    nobody = decided(())
    assert key_decision(nobody, ceiling=None, listed=True, row=row()) is nobody
    closed = decided({P.FORM_READ}, hidden=True)
    for listed in (False, True):
        got = key_decision(
            closed, ceiling=role_ceiling("EDITOR"), listed=listed, row=row()
        )
        assert got.hidden


def test_the_switch_is_off_by_default_and_only_setting_is_refused():
    assert settings.api_key_roles.ENABLED is False
    assert mode.api_key_roles_enabled() is False
    # a key with neither limit is a key as it has always been
    mode.refuse_setting_when_off()
    mode.refuse_setting_when_off(None, None)
    mode.refuse_setting_when_off(form_scope=SCOPE_ALL)
    for role, scope in (("VIEWER", None), (None, SCOPE_LISTED), ("EDITOR", "all")):
        with pytest.raises(HTTPException) as refused:
            mode.refuse_setting_when_off(role, scope)
        assert refused.value.status_code == 422
        assert refused.value.content["code"] == "api_key_roles_off"
    with pytest.raises(HTTPException):
        mode.refuse_when_off()


def test_the_switch_on_lets_a_role_and_a_list_be_set(roles_on):
    mode.refuse_setting_when_off("VIEWER", SCOPE_LISTED)
    mode.refuse_when_off()


def test_a_key_stored_before_roles_loads_unlimited_and_unknown_values_fail_closed():
    old = WorkspaceAPIKeyDocument(
        workspace_id=RecordId(), name="n", key_hash="h", prefix="bc_", created_by="u"
    )
    assert old.role is None and old.form_scope == "all"
    assert not api_access._has_limits(old)
    odd = WorkspaceAPIKeyDocument(
        workspace_id=RecordId(), name="n", key_hash="h", prefix="bc_", created_by="u",
        role="DEMIGOD", form_scope="somewhere",
    )
    assert api_access._has_limits(odd)
    assert role_ceiling(odd.role, odd.scopes) == frozenset()
    assert api_access.is_listed(odd.form_scope)


def test_the_acting_users_ceiling_is_never_part_of_a_token():
    user = User(id="u", sub="s", key_ceiling=frozenset({"form.read"}))
    assert "key_ceiling" not in user.model_dump()
    assert "key_ceiling" not in user.model_dump_json()


# =========================================================================== the decision, stored
async def test_a_role_limited_key_is_refused_what_its_role_lacks_even_for_an_admins_key(
    workspace, workspace_form, roles_on
):
    admin = await admin_creator(workspace)
    viewer = await make_key(workspace, admin, role="VIEWER")
    editor = await make_key(workspace, admin, role="EDITOR")
    plain = await make_key(workspace, admin)
    form = str(workspace_form.form_id)
    # reading is within the role
    await require_key_scope(viewer, "forms:read", form)
    # writing is not: the role's code, not the creator's
    status, body = await refusal(require_key_scope(viewer, "forms:write", form))
    assert status == 403 and body["code"] == "key_role_lacks_permission"
    await require_key_scope(editor, "forms:write", form)
    await require_key_scope(plain, "forms:write", form)
    # and by the key's own scopes, never the role: a key without the scope is
    # refused as ever
    status, body = await refusal(require_key_scope(viewer, "forms:delete", form))
    assert status == 403 and body["code"] == "missing_scope"


async def test_a_role_limited_key_is_refused_before_the_form_is_looked_at(
    workspace, roles_on
):
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, role="REVIEWER")
    # workspace level: no form named, the role alone refuses
    status, body = await refusal(require_key_scope(key, "forms:write"))
    assert status == 403 and body["code"] == "key_role_lacks_permission"


async def test_viewer_and_reviewer_keys_read_answers_with_the_scope_and_a_privacy_officer_key_never(
    workspace, workspace_form, roles_on
):
    admin = await admin_creator(workspace)
    form = str(workspace_form.form_id)
    for role in ("VIEWER", "REVIEWER"):
        key = await make_key(workspace, admin, role=role)  # holds responses:read
        await require_key_scope(key, "responses:read", form)
    officer = await make_key(workspace, admin, role="PRIVACY_OFFICER")
    status, body = await refusal(require_key_scope(officer, "responses:read", form))
    assert status == 403 and body["code"] == "key_role_lacks_permission"
    # ... and the privacy programme, which the Privacy officer holds, only for
    # a creator who holds it too (an Admin does)
    privacy = await make_key(
        workspace, admin, ("forms:read", "deletion_requests:read"), role="PRIVACY_OFFICER"
    )
    await require_key_scope(privacy, "deletion_requests:read", form)
    editor = await make_key(
        workspace, admin, ("forms:read", "deletion_requests:read"), role="EDITOR"
    )
    status, body = await refusal(require_key_scope(editor, "deletion_requests:read", form))
    assert body["code"] == "key_role_lacks_permission"


async def test_a_demoted_creator_narrows_the_key_and_the_role_never_repairs_it(
    workspace, workspace_form, roles_on
):
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, role="EDITOR")
    form = str(workspace_form.form_id)
    await require_key_scope(key, "forms:write", form)
    # the Editor-role key of an Admin who is now a Reviewer: the creator's code
    await set_roles(workspace, admin, "REVIEWER")
    status, body = await refusal(require_key_scope(key, "forms:write", form))
    assert status == 403 and body["code"] == "key_creator_lacks_permission"
    await require_key_scope(key, "forms:read", form)
    # a creator who is promoted does not widen a role-limited key
    await set_roles(workspace, admin, "ADMIN")
    viewer = await make_key(workspace, admin, role="VIEWER")
    status, body = await refusal(require_key_scope(viewer, "forms:write", form))
    assert body["code"] == "key_role_lacks_permission"


async def test_a_removed_or_disabled_creator_refuses_every_key_whatever_its_limits(
    workspace, workspace_form, roles_on
):
    form = str(workspace_form.form_id)
    for state in ("removed", "disabled"):
        creator = await admin_creator(workspace)
        key = await make_key(
            workspace, creator, role="EDITOR", form_scope=SCOPE_LISTED, forms=[form]
        )
        await require_key_scope(key, "forms:read", form)
        membership = await container.workspace_user_repo().find_workspace_user(
            workspace.id, RecordId(creator.id)
        )
        if state == "removed":
            await container.workspace_user_repo().delete_by_id(membership.id)
        else:
            membership.disabled = True
            await container.workspace_user_repo().save(membership)
        status, body = await refusal(require_key_scope(key, "forms:read", form))
        assert status == 403 and body["code"] == "key_creator_lacks_permission", state


@pytest.mark.parametrize("form_access", [False, True])
async def test_a_listed_key_opens_its_forms_only_and_others_answer_as_missing(
    workspace, workspace_form, monkeypatch, form_access
):
    monkeypatch.setattr(settings.form_access, "ENABLED", form_access)
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", True)
    other = await create_form(workspace, testUser)
    admin = await admin_creator(workspace)
    key = await make_key(
        workspace, admin, form_scope=SCOPE_LISTED, forms=[workspace_form.form_id]
    )
    listed, unlisted, missing = (
        str(workspace_form.form_id),
        str(other.form_id),
        str(RecordId()),
    )
    await require_key_scope(key, "forms:write", listed)
    # a form of the workspace the key is not listed for and a form that does
    # not exist: the very same answer, before any permission is looked at
    unlisted_answer = await refusal(require_key_scope(key, "forms:write", unlisted))
    missing_answer = await refusal(require_key_scope(key, "forms:write", missing))
    assert unlisted_answer == missing_answer == (404, "Form not found")
    assert not await api_access.key_may_use_form(key, "forms:read", unlisted)
    assert await api_access.key_may_use_form(key, "forms:read", listed)


async def test_listed_means_the_stored_flag_so_no_rows_is_nothing_and_never_everything(
    workspace, workspace_form, roles_on
):
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, form_scope=SCOPE_LISTED, forms=[])
    form = str(workspace_form.form_id)
    assert await refusal(require_key_scope(key, "forms:read", form)) == (404, "Form not found")
    assert await restrict_to_key_visible(key, [form], [P.FORM_READ]) == []
    # the last row deleted narrows to nothing
    await grant(workspace, form, key.id, ROLE_EDITOR, subject_type=SUBJECT_KEY)
    await require_key_scope(key, "forms:read", form)
    await container.form_access_grant_repo().delete_for_subject(
        workspace.id, SUBJECT_KEY, key.id
    )
    assert await refusal(require_key_scope(key, "forms:read", form)) == (404, "Form not found")


async def test_a_row_does_not_open_a_form_closed_to_the_creator(
    workspace, workspace_form, roles_on, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    await restrict(workspace, workspace_form.form_id)
    form = str(workspace_form.form_id)
    key = await make_key(
        workspace, editor, form_scope=SCOPE_LISTED, forms=[form]
    )
    assert await refusal(require_key_scope(key, "forms:read", form)) == (404, "Form not found")
    # the creator is given a Viewer grant: the key holds, at most, that
    await grant(workspace, form, editor.id, ROLE_VIEWER)
    await require_key_scope(key, "forms:read", form)
    status, body = await refusal(require_key_scope(key, "forms:write", form))
    assert status == 403 and body["code"] == "key_creator_lacks_permission"


async def test_a_row_ceiling_refuses_what_it_does_not_allow_with_the_roles_code(
    workspace, workspace_form, roles_on
):
    admin = await admin_creator(workspace)
    form = str(workspace_form.form_id)
    key = await make_key(
        workspace,
        admin,
        ("forms:read", "forms:write", "forms:delete"),
        form_scope=SCOPE_LISTED,
        forms=[form],
        row_role=ROLE_REVIEWER,
    )
    await require_key_scope(key, "forms:read", form)
    status, body = await refusal(require_key_scope(key, "forms:write", form))
    assert status == 403 and body["code"] == "key_role_lacks_permission"
    # a listed key never deletes, whatever its scope says
    editor_row = await make_key(
        workspace, admin, ("forms:read", "forms:delete"),
        form_scope=SCOPE_LISTED, forms=[form],
    )
    status, body = await refusal(require_key_scope(editor_row, "forms:delete", form))
    assert body["code"] == "key_role_lacks_permission"
    decided_on = await key_permissions_on_form(editor_row, form)
    assert P.FORM_DELETE not in decided_on.permissions and decided_on.source == SOURCE_KEY


async def test_a_key_row_of_another_key_or_workspace_opens_nothing(
    workspace, workspace_form, workspace_1, roles_on
):
    admin = await admin_creator(workspace)
    form = str(workspace_form.form_id)
    mine = await make_key(workspace, admin, form_scope=SCOPE_LISTED)
    theirs = await make_key(
        workspace, admin, form_scope=SCOPE_LISTED, forms=[form]
    )
    assert theirs.id != mine.id
    assert await refusal(require_key_scope(mine, "forms:read", form)) == (404, "Form not found")
    # a row of the same key id in another workspace is another workspace's row
    await grant(
        workspace_1, form, mine.id, ROLE_EDITOR, subject_type=SUBJECT_KEY
    )
    assert await refusal(require_key_scope(mine, "forms:read", form)) == (404, "Form not found")


async def test_the_lists_narrow_to_the_key_before_anything_is_counted(
    workspace, workspace_form, roles_on
):
    other = await create_form(workspace, testUser)
    admin = await admin_creator(workspace)
    a, b = str(workspace_form.form_id), str(other.form_id)
    listed = await make_key(workspace, admin, form_scope=SCOPE_LISTED, forms=[b])
    plain = await make_key(workspace, admin)
    viewer = await make_key(workspace, admin, role="VIEWER")
    assert await restrict_to_key_visible(listed, [a, b], [P.FORM_READ]) == [b]
    assert await restrict_to_key_visible(listed, [a, b], [P.FORM_EDIT]) == [b]
    assert await restrict_to_key_visible(listed, [], [P.FORM_READ]) == []
    assert await restrict_to_key_visible(plain, [a, b], [P.FORM_READ]) == [a, b]
    # a role that lacks the permission sees no form for it
    assert await restrict_to_key_visible(viewer, [a, b], [P.FORM_EDIT]) == []
    assert await restrict_to_key_visible(viewer, [a, b], [P.FORM_READ]) == [a, b]
    # the row's ceiling counts too: a Viewer row does not list forms to edit
    narrow = await make_key(
        workspace, admin, form_scope=SCOPE_LISTED, forms=[a, b], row_role=ROLE_VIEWER
    )
    assert await restrict_to_key_visible(narrow, [a, b], [P.FORM_READ]) == [a, b]
    assert await restrict_to_key_visible(narrow, [a, b], [P.FORM_EDIT]) == []


async def test_a_key_never_does_more_than_its_creator_in_any_combination(
    workspace, workspace_form, roles_on, switch_on
):
    """Whatever the role and the scope, the key's permissions on a form are a
    subset of what its creator holds there right now."""
    form = str(workspace_form.form_id)
    creators = {
        "viewer": await add_member(workspace, "VIEWER"),
        "reviewer": await add_member(workspace, "REVIEWER"),
        "editor": await add_member(workspace, "COLLABORATOR"),
        "admin": await admin_creator(workspace),
    }
    service = container.authorization_service()
    for creator in creators.values():
        held = await service.effective_permissions(creator, workspace.id, form_id=form)
        for role in (None, "EDITOR", "REVIEWER", "VIEWER", "PRIVACY_OFFICER", "BOGUS"):
            for scope, forms in ((SCOPE_ALL, []), (SCOPE_LISTED, [form]), (SCOPE_LISTED, [])):
                for row_role in (ROLE_EDITOR, ROLE_VIEWER):
                    key = await make_key(
                        workspace, creator, READ_ALL, role=role,
                        form_scope=scope, forms=forms, row_role=row_role,
                    )
                    got = await key_permissions_on_form(key, form)
                    assert got.permissions <= held, (role, scope, forms)
                    ceiling = role_ceiling(role, key.scopes)
                    if ceiling is not None:
                        assert got.permissions <= ceiling
                    # the acting user the services authorize as is capped too
                    capped = await service.effective_permissions(
                        acting_user(key), workspace.id, form_id=form
                    )
                    assert capped <= held
                    if ceiling is not None:
                        assert capped <= ceiling


# =========================================================================== defence in depth
async def test_the_acting_user_carries_the_roles_ceiling_into_the_services(
    workspace, workspace_form, roles_on, switch_on
):
    admin = await admin_creator(workspace)
    form = str(workspace_form.form_id)
    service = container.authorization_service()
    viewer = await make_key(workspace, admin, role="VIEWER")
    plain = await make_key(workspace, admin)
    assert plain and acting_user(plain).key_ceiling is None
    assert acting_user(viewer).key_ceiling == frozenset(
        p.value for p in role_ceiling("VIEWER", viewer.scopes)
    )
    # a service that authorizes as the creator is held to the key's role
    capped = acting_user(viewer)
    await service.authorize(capped, P.FORM_READ, workspace.id, form_id=form)
    for permission in (P.FORM_EDIT, P.FORM_CREATE, P.FORM_DELETE):
        with pytest.raises(HTTPException) as refused:
            await service.authorize(capped, permission, workspace.id, form_id=form)
        assert refused.value.status_code == 403
        assert not await service.has_permission(capped, permission, workspace.id)
        assert permission in await service.effective_permissions(
            acting_user(viewer, with_ceiling=False), workspace.id
        )
    # the lists of forms obey it too
    assert await service.visible_form_ids(capped, workspace.id, P.FORM_EDIT) == frozenset()
    assert await service.restrict_to_visible(capped, workspace.id, [form], P.FORM_EDIT) == []
    base = await service.base_access(capped, workspace.id)
    assert base.permissions <= role_ceiling("VIEWER", viewer.scopes)
    # a session user is not capped
    assert P.FORM_EDIT in await service.effective_permissions(admin, workspace.id)


async def test_a_grant_to_the_creator_cannot_lift_the_key_above_its_roles_ceiling(
    workspace, workspace_form, roles_on, switch_on
):
    viewer_member = await add_member(workspace, "VIEWER")
    form = str(workspace_form.form_id)
    await grant(workspace, form, viewer_member.id, ROLE_EDITOR)
    service = container.authorization_service()
    # the creator holds an Editor grant: edits the form
    assert P.FORM_EDIT in await service.effective_permissions(
        viewer_member, workspace.id, form_id=form
    )
    key = await make_key(workspace, viewer_member, role="VIEWER")
    free = await make_key(workspace, viewer_member)
    # what each key may do on the form: the creator's grant, narrowed by the role
    assert P.FORM_EDIT in (await key_permissions_on_form(free, form)).permissions
    assert P.FORM_EDIT not in (await key_permissions_on_form(key, form)).permissions
    assert P.FORM_EDIT not in await service.effective_permissions(
        acting_user(key), workspace.id, form_id=form
    )
    assert P.FORM_EDIT in await service.effective_permissions(
        acting_user(free), workspace.id, form_id=form
    )


# =========================================================================== off
async def test_off_an_unlimited_key_reads_nothing_new_and_behaves_as_before(
    workspace, workspace_form, roles_off, switch_off, monkeypatch
):
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin)
    form = str(workspace_form.form_id)
    repo = container.form_access_grant_repo()

    def forbidden(*args, **kwargs):
        raise AssertionError("an unlimited key read a key row")

    for name in ("for_key", "for_key_on_form", "replace_for_key"):
        monkeypatch.setattr(repo, name, forbidden)
    with statements() as seen:
        await require_key_on_form(key, "forms:write", form, must_exist=True)
        assert await restrict_to_key_visible(key, [form], [P.FORM_READ]) == [form]
    assert seen == []
    assert acting_user(key).key_ceiling is None
    # the scope check is the same one as before: one membership read, and the
    # creator's workspace permissions
    await require_key_scope(key, "forms:write", form)


async def test_off_only_a_limited_key_reads_its_row(
    workspace, workspace_form, roles_on, switch_off
):
    admin = await admin_creator(workspace)
    form = str(workspace_form.form_id)
    plain = await make_key(workspace, admin)
    listed = await make_key(workspace, admin, form_scope=SCOPE_LISTED, forms=[form])
    for key in (plain, listed):  # warm what is cached
        await require_key_scope(key, "forms:read", form)
    with statements() as seen_plain:
        await require_key_scope(plain, "forms:read", form)
    with statements() as seen_listed:
        await require_key_scope(listed, "forms:read", form)
    assert not [s for s in seen_plain if "form_access_grants" in s]
    # one indexed read of the key's row, nothing else of the new tables
    assert len([s for s in seen_listed if "form_access_grants" in s]) == 1


async def test_off_the_limits_already_stored_are_still_enforced(
    workspace, workspace_form, roles_off, switch_off
):
    """Switching the feature off never widens a key."""
    other = await create_form(workspace, testUser)
    admin = await admin_creator(workspace)
    form, unlisted = str(workspace_form.form_id), str(other.form_id)
    viewer = await make_key(workspace, admin, role="VIEWER")
    status, body = await refusal(require_key_scope(viewer, "forms:write", form))
    assert status == 403 and body["code"] == "key_role_lacks_permission"
    listed = await make_key(workspace, admin, form_scope=SCOPE_LISTED, forms=[form])
    await require_key_scope(listed, "forms:read", form)
    assert await refusal(require_key_scope(listed, "forms:read", unlisted)) == (
        404, "Form not found",
    )
    assert await restrict_to_key_visible(listed, [form, unlisted], [P.FORM_READ]) == [form]
    # a role this code does not know refuses everything
    odd = await make_key(workspace, admin, role="DEMIGOD")
    status, body = await refusal(require_key_scope(odd, "forms:read", form))
    assert body["code"] == "key_role_lacks_permission"


# =========================================================================== end to end
def _auth(key):
    return {"Authorization": f"Bearer {TOKENS[str(key.id)]}"}


async def _spec_form(client, owner, title):
    """A form the public API can show (built from pages), made through it."""
    created = await client.post(
        f"{BASE}/forms", json={**SPEC, "title": title}, headers=_auth(owner)
    )
    assert created.status_code == 201, created.text
    return created.json()["formId"]


async def test_the_public_api_answers_a_listed_keys_other_forms_like_missing_ones(
    client: AsyncClient, workspace, roles_on
):
    owner = await make_key(workspace, testUser)
    first = await _spec_form(client, owner, "First")
    second = await _spec_form(client, owner, "Second")
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, form_scope=SCOPE_LISTED, forms=[first])
    opened = await client.get(f"{BASE}/forms/{first}", headers=_auth(key))
    assert opened.status_code == 200, opened.text
    refused = await client.get(f"{BASE}/forms/{second}", headers=_auth(key))
    ghost = await client.get(f"{BASE}/forms/{RecordId()}", headers=_auth(key))
    assert refused.status_code == ghost.status_code == 404
    assert refused.json() == ghost.json()
    listing = (await client.get(f"{BASE}/forms", headers=_auth(key))).json()
    assert {i["formId"] for i in listing["items"]} == {first}
    assert listing["total"] == 1
    # a role-limited key: reading works, writing is the role's 403
    viewer = await make_key(workspace, admin, role="VIEWER")
    assert (await client.get(f"{BASE}/forms/{second}", headers=_auth(viewer))).status_code == 200
    written = await client.post(
        f"{BASE}/forms/{second}/ops/dry-run",
        json={"ops": [{"op": "update_form_info", "title": "x"}]},
        headers=_auth(viewer),
    )
    assert written.status_code == 403
    assert written.json()["code"] == "key_role_lacks_permission"
    # the owner's key, with no limit, is as before
    assert (await client.get(f"{BASE}/forms/{second}", headers=_auth(owner))).status_code == 200


async def test_using_and_revoking_a_key_keep_its_limits(workspace, roles_on):
    """Both rewrite the stored key: they must carry the role and the form
    scope along (a release that does not know the two fields drops them the same
    way, which is why limited keys are revoked before a rollback)."""
    from backend.app.services.ai.api_keys import APIKeyService

    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, role="VIEWER", form_scope=SCOPE_LISTED)
    repo = container.workspace_api_key_repo()
    used = await APIKeyService.authenticate(TOKENS[str(key.id)])
    assert (used.role, used.form_scope) == ("VIEWER", SCOPE_LISTED)
    stored = await repo.get_or_404(key.id)
    assert (stored.role, stored.form_scope, stored.last_used_at is not None) == (
        "VIEWER", SCOPE_LISTED, True,
    )
    await container.api_key_service().revoke_key(workspace.id, str(key.id), testUser)
    stored = await repo.get_or_404(key.id)
    assert stored.revoked and (stored.role, stored.form_scope) == ("VIEWER", SCOPE_LISTED)
