"""With ``FORM_ACCESS_ENABLED`` off form-level access adds nothing: not a
decision, not a query. With it on, a form's facts are read once per request and
never remembered across requests."""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import ROLE_EDITOR
from backend.app.services.authorization_service import (
    EDITOR_PERMISSIONS,
    AuthorizationService,
)
from backend.app.services.form_access.mode import (
    OFF_CODE,
    form_access_enabled,
    refuse_when_off,
)
from backend.app.services.request_context import bind_request, unbind_request
from backend.config import settings
from backend.config.application import Application
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import add_member, grant, restrict, team_with

P = Permission
NEW_TABLES = ("form_access_grants", "member_group_members", "member_groups")


@contextmanager
def statements():
    """Every SQL statement the database sees while the block runs."""
    seen = []
    sync_engine = container.pg_engine().sync_engine

    def record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    event.listen(sync_engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(sync_engine, "before_cursor_execute", record)


def touching_new_tables(seen):
    return [s for s in seen if any(table in s for table in NEW_TABLES)]


def plain_authorization() -> AuthorizationService:
    """The service as it was before form-level access: no resolver wired."""
    return AuthorizationService(
        workspace_repo=container.workspace_repo(),
        workspace_user_repo=container.workspace_user_repo(),
        workspace_form_repo=container.workspace_form_repo(),
        sso_policy=lambda: container.sso_policy_service(),
    )


def test_the_switch_is_off_by_default():
    assert Application.model_fields["form_access"].default.ENABLED is False
    assert settings.form_access.ENABLED is False
    assert form_access_enabled() is False


def test_the_routes_that_change_access_answer_422_while_it_is_off(monkeypatch):
    from backend.app.exceptions import HTTPException

    with pytest.raises(HTTPException) as refused:
        refuse_when_off()
    assert refused.value.status_code == 422
    assert refused.value.content["code"] == OFF_CODE
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    refuse_when_off()


async def test_off_the_decision_reads_no_grant_no_team_and_no_mode(
    switch_off, workspace, workspace_form, monkeypatch
):
    """Stored grants, teams and a restricted mode exist, and not one query
    touches the new tables: the same statements the service made before this
    feature, in the same number."""
    editor = await add_member(workspace, "COLLABORATOR")
    viewer = await add_member(workspace, "VIEWER")
    await restrict(workspace, workspace_form.form_id)
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
    await team_with(workspace, editor)

    # and the repositories are never so much as called
    def forbidden(*args, **kwargs):
        raise AssertionError("form-level access read a store while switched off")

    for repo in (container.form_access_grant_repo(), container.member_group_repo()):
        for name in ("for_user_on_form", "for_user", "group_ids_of", "list_for_form", "many", "one"):
            if hasattr(repo, name):
                monkeypatch.setattr(repo, name, forbidden)

    authz, before = container.authorization_service(), plain_authorization()
    for user in (testUser, editor, viewer):
        for call in (
            lambda a: a.authorize(
                user, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
            ),
            lambda a: a.has_permission(
                user, P.RESPONSE_READ, workspace.id, form_id=workspace_form.form_id
            ),
            lambda a: a.effective_permissions(
                user, workspace.id, form_id=workspace_form.form_id
            ),
        ):
            with statements() as with_feature:
                await call(authz)
            with statements() as without:
                await call(before)
            assert not touching_new_tables(with_feature)
            assert len(with_feature) == len(without)
    # and the decisions are exactly the role's
    assert await authz.effective_permissions(
        editor, workspace.id, form_id=workspace_form.form_id
    ) == EDITOR_PERMISSIONS


async def test_off_equals_the_roles_for_every_role_with_data_stored(
    switch_off, workspace, workspace_form
):
    await restrict(workspace, workspace_form.form_id)
    authz = container.authorization_service()
    for roles in (["VIEWER"], ["REVIEWER"], ["COLLABORATOR"], ["PRIVACY_OFFICER"], ["ADMIN"], ["OWNER"], []):
        user = await add_member(workspace, *roles)
        await grant(workspace, workspace_form.form_id, user.id, ROLE_EDITOR, export=True)
        assert await authz.effective_permissions(
            user, workspace.id, form_id=workspace_form.form_id
        ) == await authz.effective_permissions(user, workspace.id)


async def test_on_an_owner_reads_nothing_either(switch_on, workspace, workspace_form):
    """Owners and Admins pass without a decision: the new tables are not read."""
    admin = await add_member(workspace, "ADMIN")
    authz = container.authorization_service()
    for user in (testUser, admin):
        with statements() as seen:
            await authz.authorize(
                user, P.FORM_EDIT, workspace.id, form_id=workspace_form.form_id
            )
        assert not touching_new_tables(seen)


async def test_on_a_member_costs_one_extra_grant_query(switch_on, workspace, workspace_form):
    viewer = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()
    with statements() as seen:
        await authz.authorize(
            viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
        )
    # one query reads direct and team grants together
    grants = [s for s in seen if "form_access_grants" in s]
    assert len(grants) == 1
    # the form lookup of the decision stands in for the 404 check's own
    assert len([s for s in seen if "workspace_forms" in s]) == 1


async def test_a_request_reads_a_forms_facts_once(switch_on, workspace, workspace_form):
    viewer = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()

    token = bind_request({"method": "GET"})
    try:
        with statements() as seen:
            for _ in range(4):
                await authz.authorize(
                    viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
                )
        assert len([s for s in seen if "form_access_grants" in s]) == 1
    finally:
        unbind_request(token)

    # outside a request nothing is remembered
    with statements() as seen:
        for _ in range(3):
            await authz.authorize(
                viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
            )
    assert len([s for s in seen if "form_access_grants" in s]) == 3


async def test_nothing_is_remembered_from_one_request_to_the_next(
    switch_on, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()

    token = bind_request({})
    try:
        assert P.FORM_EDIT not in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
    finally:
        unbind_request(token)
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)

    token = bind_request({})  # the next request
    try:
        assert P.FORM_EDIT in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
    finally:
        unbind_request(token)


async def test_a_change_within_a_request_forgets_what_it_read(
    switch_on, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()
    token = bind_request({})
    try:
        assert P.FORM_EDIT not in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
        await grant(workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR)
        # still the remembered answer until the writer says it changed something
        assert P.FORM_EDIT not in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
        container.form_access_service().invalidate()
        assert P.FORM_EDIT in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
    finally:
        unbind_request(token)


async def test_a_role_change_within_a_request_is_seen(switch_on, workspace, workspace_form):
    """Only the form's facts are remembered, never the member's role."""
    from common.ids import RecordId

    viewer = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()
    token = bind_request({})
    try:
        assert P.FORM_EDIT not in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
        membership = await container.workspace_user_repo().find_workspace_user(
            workspace.id, RecordId(viewer.id)
        )
        membership.roles = ["COLLABORATOR"]
        await container.workspace_user_repo().save(membership)
        assert P.FORM_EDIT in await authz.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
    finally:
        unbind_request(token)


async def test_off_every_form_is_visible_to_whoever_holds_the_permission(
    switch_off, workspace, workspace_form
):
    viewer = await add_member(workspace, "VIEWER")
    await restrict(workspace, workspace_form.form_id)
    for service in (container.authorization_service(), plain_authorization()):
        assert await service.visible_form_ids(viewer, workspace.id, P.FORM_READ) is None
        assert await service.visible_form_ids(viewer, workspace.id, P.FORM_EDIT) == frozenset()


async def test_an_unwired_resolver_fails_closed_while_the_switch_is_on(
    workspace, workspace_form, monkeypatch
):
    viewer = await add_member(workspace, "VIEWER")
    service = plain_authorization()
    # off: nothing needs it
    await service.authorize(viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    with pytest.raises(RuntimeError):
        await service.authorize(
            viewer, P.FORM_READ, workspace.id, form_id=workspace_form.form_id
        )
    with pytest.raises(RuntimeError):
        await service.effective_permissions(
            viewer, workspace.id, form_id=workspace_form.form_id
        )
    # a workspace-level question needs no form decision
    assert await service.effective_permissions(viewer, workspace.id)
