"""Permission matrix: each workspace endpoint that goes through
``AuthorizationService.authorize`` against the owner, an admin, a collaborator,
a non-member and a disabled (admin) membership.

The regression net of docs/enterprise-access-model.md: a new workspace
endpoint gets a row here. A role is *refused* when the endpoint answers 403
with the authorization message. An allowed role never gets a 403 (unless the
row names the non-authorization 403 it expects, ``ai_not_enabled`` while AI
is off) and never a 500; rows with ``ok`` expect that exact status. The
``.on`` AI rows run with AI enabled and a fake provider, which refused roles
never reach.
"""

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.invitation_request import InvitationRequest
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.form_import import FormImportDocument
from backend.app.schemas.workspace_domain import WorkspaceDomainDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services.authorization_service import (
    ALL_PERMISSIONS,
    DISABLED_WORKSPACE_OWNER_PERMISSIONS,
    MEMBER_PERMISSIONS,
)
from backend.app.services.form_service import FormService
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.test_form_ai_insights import _seed_form_and_responses
from tests.app.controllers.data import (
    formData,
    formResponse,
    invited_user,
    testUser,
    testUser1,
    testUser2,
)

OWNER, ADMIN, COLLABORATOR, NON_MEMBER, DISABLED = (
    "owner",
    "admin",
    "collaborator",
    "non_member",
    "disabled_member",
)
ROLES = (OWNER, ADMIN, COLLABORATOR, NON_MEMBER, DISABLED)

admin_user = User(id=str(PydanticObjectId()), sub="matrix-admin@example.com")
# an ADMIN whose membership is disabled (a downgraded owner's workspace): #770
disabled_user = User(id=str(PydanticObjectId()), sub="matrix-disabled@example.com")
removable_user = User(id=str(PydanticObjectId()), sub="matrix-removable@example.com")

USERS: Dict[str, User] = {
    OWNER: testUser,
    ADMIN: admin_user,
    COLLABORATOR: invited_user,
    NON_MEMBER: testUser1,
    DISABLED: disabled_user,
}

MEMBERS = frozenset({OWNER, ADMIN, COLLABORATOR})
ADMINS = frozenset({OWNER, ADMIN})
OWNER_ONLY = frozenset({OWNER})

NOT_AUTHORIZED = "You are not authorized to perform this action."


def _oid() -> str:
    return str(PydanticObjectId())


@dataclass(frozen=True)
class Case:
    name: str
    method: str
    path: str  # formatted with the context: {ws} {form} {response} {group} ...
    allowed: FrozenSet[str]
    request: Callable[[dict], dict] = field(default=lambda c: {})
    # the body a refused role gets (authorize's message unless stated)
    refused_body: str = MESSAGE_FORBIDDEN
    # a 403 an allowed role may get that is not about permissions
    allowed_403: Optional[str] = None
    # the exact status an allowed role gets
    ok: Optional[int] = None
    # run with AI enabled for the workspace and the form, the fake provider
    # answering with these replies
    ai_replies: Optional[Tuple] = None


AI_OFF = "ai_not_enabled"
CHAT_REPLY = json.dumps({"reply": "Done.", "ops": []})
REVIEW_REPLY = json.dumps({"summary": "Looks fine.", "findings": []})
INSIGHTS_REPLY = json.dumps(
    {
        "summary": "Respondents are happy.",
        "themes": [],
        "actionable": [],
        "sentiment": "Positive.",
    }
)
GENERATED_FORM = {"title": "Generated", "description": "", "fields": []}
TEMPLATE_BODY = json.dumps({"title": "Matrix template", "fields": []})


W = "/api/v1/workspaces/{ws}"
F = W + "/forms/{form}"

CASES = [
    # --- workspace settings
    Case("workspace.patch", "PATCH", W, OWNER_ONLY, lambda c: {"data": {"title": "x"}}),
    Case(
        "workspace.theme_presets",
        "PATCH",
        W + "/theme-presets",
        ADMINS,
        lambda c: {"json": []},
    ),
    Case("workspace.custom_domain.delete", "DELETE", W + "/custom-domain", ADMINS),
    Case("workspace.custom_domain.verify", "GET", W + "/verify-domain", ADMINS),
    Case(
        "workspace.custom_domain.recheck", "POST", W + "/custom-domain/recheck", ADMINS
    ),
    Case("workspace.stats", "GET", W + "/stats", MEMBERS),
    # --- AI settings, profile, keys
    Case("ai.settings.get", "GET", W + "/ai-settings", MEMBERS),
    Case(
        "ai.settings.put",
        "PUT",
        W + "/ai-settings",
        ADMINS,
        lambda c: {"json": {"enabled": False}},
    ),
    Case("ai.profile.get", "GET", W + "/ai-profile", MEMBERS),
    Case(
        "ai.profile.put",
        "PUT",
        W + "/ai-profile",
        ADMINS,
        lambda c: {"json": {"about": "Org"}},
    ),
    Case(
        "ai.memory.settings",
        "PUT",
        W + "/ai-memory/settings",
        MEMBERS,
        lambda c: {"json": {"learnPreferences": False}},
    ),
    Case("api_keys.list", "GET", W + "/api-keys", ADMINS),
    Case(
        "api_keys.create",
        "POST",
        W + "/api-keys",
        ADMINS,
        lambda c: {"json": {"name": "matrix", "scopes": ["forms:read"]}},
    ),
    Case("api_keys.revoke", "DELETE", W + "/api-keys/{api_key}", ADMINS),
    # --- members and invitations
    Case("members.list", "GET", W + "/members", ADMINS),
    Case("members.invitations.list", "GET", W + "/members/invitations", ADMINS),
    Case(
        "members.invitations.create",
        "POST",
        W + "/members/invitations",
        ADMINS,
        lambda c: {"json": {"email": "new@example.com", "role": "COLLABORATOR"}},
    ),
    Case(
        "members.invitations.delete",
        "DELETE",
        W + "/members/invitations/{invitation}",
        ADMINS,
        ok=200,
    ),
    Case("members.remove", "DELETE", W + "/members/{removable}", ADMINS),
    # --- verified email domains (security.manage)
    Case("domains.list", "GET", W + "/domains", ADMINS, ok=200),
    Case(
        "domains.claim",
        "POST",
        W + "/domains",
        ADMINS,
        lambda c: {"json": {"domain": "matrix-claim.org"}},
        ok=201,
    ),
    Case("domains.verify", "POST", W + "/domains/{domain}/verify", ADMINS, ok=200),
    Case("domains.delete", "DELETE", W + "/domains/{domain}", ADMINS, ok=204),
    Case(
        # a claim of another workspace: 404 once past the permission check
        "domains.verify.other_workspace",
        "POST",
        W + "/domains/{other_domain}/verify",
        ADMINS,
        ok=404,
    ),
    Case(
        "domains.delete.other_workspace",
        "DELETE",
        W + "/domains/{other_domain}",
        ADMINS,
        ok=404,
    ),
    # --- forms
    Case("forms.list", "GET", W + "/forms", MEMBERS),
    Case(
        "forms.create",
        "POST",
        W + "/forms",
        MEMBERS,
        lambda c: {"data": {"form_body": json.dumps(formData)}},
    ),
    Case(
        "forms.update",
        "PATCH",
        F,
        MEMBERS,
        lambda c: {"data": {"form_body": json.dumps(formData)}},
    ),
    Case("forms.duplicate", "POST", F + "/duplicate", MEMBERS),
    Case("forms.publish", "POST", F + "/publish", MEMBERS),
    Case("forms.delete", "DELETE", F, MEMBERS),
    Case(
        "forms.settings",
        "PATCH",
        F + "/settings",
        MEMBERS,
        lambda c: {"json": {"pinned": True}},
    ),
    Case(
        "forms.settings.hidden",
        "PATCH",
        F + "/settings",
        MEMBERS,
        lambda c: {"json": {"hidden": True}},
    ),
    Case(
        "forms.settings.feedback",
        "PATCH",
        F + "/settings",
        MEMBERS,
        lambda c: {"json": {"respondentFeedbackEnabled": True}},
    ),
    Case(
        "forms.settings.private",
        "PATCH",
        F + "/settings",
        MEMBERS,
        lambda c: {"json": {"private": True}},
        ok=200,
    ),
    Case(
        "forms.groups.add",
        "PATCH",
        F + "/groups/add",
        MEMBERS,
        lambda c: {"json": {"group_ids": [c["group"]]}},
    ),
    Case(
        "forms.groups.remove",
        "DELETE",
        F + "/groups",
        MEMBERS,
        lambda c: {"params": {"group_id": c["group"]}},
    ),
    Case(
        "forms.actions.add",
        "POST",
        F + "/actions",
        MEMBERS,
        lambda c: {"json": {"action_id": c["action"]}},
        ok=200,
    ),
    Case(
        "forms.actions.update",
        "PATCH",
        F + "/actions",
        MEMBERS,
        lambda c: {"json": {"actionId": _oid(), "updateType": "enable"}},
    ),
    Case("forms.actions.remove", "DELETE", F + "/actions/{random}", MEMBERS),
    Case("forms.as_template", "POST", W + "/form/{form}/template", MEMBERS),
    Case(
        "templates.list",
        "GET",
        "/api/v1/templates",
        MEMBERS,
        lambda c: {"params": {"workspace_id": c["ws"]}},
    ),
    Case("templates.delete", "DELETE", W + "/template/{template}", MEMBERS, ok=200),
    Case(
        "templates.create",
        "POST",
        W + "/template",
        MEMBERS,
        lambda c: {"data": {"template_body": TEMPLATE_BODY}},
        ok=200,
    ),
    Case(
        "templates.update",
        "PATCH",
        W + "/template/{template}",
        MEMBERS,
        lambda c: {"data": {"template_body": TEMPLATE_BODY}},
        ok=200,
    ),
    Case(
        "templates.settings",
        "PATCH",
        W + "/template/{template}/settings",
        MEMBERS,
        lambda c: {"json": {"isPublic": False}},
        ok=200,
    ),
    Case("templates.import", "POST", W + "/template/{template}/import", MEMBERS),
    Case(
        "templates.create_form",
        "POST",
        W + "/template/{template}",
        MEMBERS,
        ok=200,
    ),
    # --- AI on forms
    Case(
        "ai.create_form",
        "POST",
        W + "/forms/ai",
        MEMBERS,
        lambda c: {"json": {"prompt": "A survey"}},
        allowed_403=AI_OFF,
    ),
    Case(
        "ai.create_form.on",
        "POST",
        W + "/forms/ai",
        MEMBERS,
        lambda c: {"json": {"prompt": "A survey"}},
        ok=200,
        ai_replies=(GENERATED_FORM,),
    ),
    Case(
        "ai.chat",
        "POST",
        F + "/ai/chat",
        MEMBERS,
        lambda c: {"json": {"message": "Add a question"}},
        allowed_403=AI_OFF,
    ),
    Case(
        "ai.chat.on",
        "POST",
        F + "/ai/chat",
        MEMBERS,
        lambda c: {"json": {"message": "Add a question"}},
        ok=200,
        ai_replies=(CHAT_REPLY,),
    ),
    Case(
        "ai.review",
        "POST",
        F + "/ai/review",
        MEMBERS,
        lambda c: {"json": {}},
        allowed_403=AI_OFF,
    ),
    Case(
        "ai.review.on",
        "POST",
        F + "/ai/review",
        MEMBERS,
        lambda c: {"json": {}},
        ok=200,
        ai_replies=(REVIEW_REPLY,),
    ),
    Case("ai.insights.get", "GET", F + "/ai/insights", MEMBERS, ok=200),
    Case(
        "ai.insights.generate",
        "POST",
        F + "/ai/insights",
        MEMBERS,
        lambda c: {"json": {}},
        allowed_403=AI_OFF,
    ),
    Case(
        "ai.insights.generate.on",
        "POST",
        F + "/ai/insights",
        MEMBERS,
        lambda c: {"json": {}},
        ok=200,
        ai_replies=(INSIGHTS_REPLY,),
    ),
    Case(
        "ai.insights.settings",
        "PUT",
        F + "/ai/insights/settings",
        ADMINS,
        lambda c: {"json": {"enabled": False}},
    ),
    # --- responses
    Case("responses.form", "GET", F + "/submissions", MEMBERS),
    Case(
        "responses.form.deletion_requests",
        "GET",
        F + "/submissions",
        MEMBERS,
        lambda c: {"params": {"request_for_deletion": True}},
    ),
    Case("responses.form.all", "GET", F + "/all-submissions", MEMBERS),
    Case("responses.workspace", "GET", W + "/all-submissions", MEMBERS),
    Case(
        "responses.workspace.deletion_requests",
        "GET",
        W + "/all-submissions",
        MEMBERS,
        lambda c: {"params": {"request_for_deletion": True}},
    ),
    Case(
        "responses.one",
        "GET",
        W + "/submissions/{response}",
        MEMBERS,
        refused_body=NOT_AUTHORIZED,
    ),
    Case("responses.delete", "DELETE", F + "/response/{response}", MEMBERS),
    Case(
        "responses.internal_answers",
        "PATCH",
        F + "/submissions/{response}/internal-answers",
        MEMBERS,
        lambda c: {"json": {"answers": {"not-a-field": None}}},
    ),
    Case(
        "responses.feedback",
        "POST",
        F + "/submissions/{response}/feedback",
        MEMBERS,
        lambda c: {"json": {"message": "Thanks"}},
    ),
    Case("responses.flow_analytics", "GET", F + "/flow-analytics", MEMBERS),
    Case(
        "analytics.umami_stats",
        "GET",
        "/api/v1/{name}/forms/{slug}/stats",
        MEMBERS,
        lambda c: {"params": {"start_at": 1, "end_at": 2}},
    ),
    # --- responders (data subjects) and their tags
    Case("responders.list", "GET", W + "/responders", MEMBERS),
    Case("responders.tags.list", "GET", W + "/responders/tags", MEMBERS),
    Case(
        "responders.tags.create",
        "POST",
        W + "/responders/tags",
        MEMBERS,
        lambda c: {"json": {"title": "vip"}},
    ),
    Case(
        "responders.patch",
        "PATCH",
        W + "/responders",
        MEMBERS,
        lambda c: {"params": {"email": testUser2.sub}, "json": {"tags": [_oid()]}},
    ),
    # --- responder groups
    Case("groups.list", "GET", "/api/v1/{ws}/responder-groups", MEMBERS),
    Case("groups.get", "GET", "/api/v1/{ws}/responder-groups/{group}", MEMBERS),
    Case(
        "groups.create",
        "POST",
        "/api/v1/{ws}/responder-groups",
        ADMINS,
        lambda c: {"params": {"name": "New group"}},
    ),
    Case(
        "groups.update",
        "PATCH",
        "/api/v1/{ws}/responder-groups/{group}",
        ADMINS,
        lambda c: {"params": {"name": "Renamed"}},
    ),
    Case(
        "groups.emails.add",
        "PATCH",
        "/api/v1/{ws}/responder-groups/{group}/emails",
        ADMINS,
        lambda c: {"json": ["b@example.com"]},
    ),
    Case(
        "groups.emails.remove",
        "DELETE",
        "/api/v1/{ws}/responder-groups/{group}/emails",
        ADMINS,
        lambda c: {"json": ["a@example.com"]},
    ),
    Case("groups.delete", "DELETE", "/api/v1/{ws}/responder-groups/{group}", ADMINS),
    # --- consent catalog
    Case("consent.list", "GET", "/api/v1/{ws}/consent", MEMBERS),
    Case(
        "consent.create",
        "POST",
        "/api/v1/{ws}/consent",
        MEMBERS,
        lambda c: {
            "json": {
                "title": "Marketing",
                "type": "checkbox",
                "category": "purpose_of_the_form",
            }
        },
    ),
    # --- media library and PDF imports
    Case("media.list", "GET", W + "/media", MEMBERS),
    Case("media.delete", "DELETE", W + "/media/{media}", MEMBERS, ok=200),
    Case("pdf_imports.list", "GET", W + "/form-imports", MEMBERS),
    Case("pdf_imports.ai_provider", "GET", W + "/form-imports/ai", MEMBERS),
    Case("pdf_imports.get", "GET", W + "/form-imports/{import}", MEMBERS, ok=200),
    Case(
        "pdf_imports.create",
        "POST",
        W + "/form-imports",
        MEMBERS,
        # refused by the upload check (not a document) after authorization
        lambda c: {"files": {"file": ("notes.txt", b"not a document", "text/plain")}},
        ok=400,
    ),
]


@pytest.fixture()
def outside_services():
    """The auth service, S3, user details and Umami are outside the test."""
    aws = container.aws_service()
    with patch(
        "common.services.http_client.HttpClient.get",
        AsyncMock(return_value={"users_info": []}),
    ), patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ), patch.object(
        aws, "upload_file_to_s3", AsyncMock(return_value="https://s3/x")
    ), patch.object(
        aws, "delete_file_from_s3", MagicMock()
    ), patch.object(
        aws, "delete_folder_from_s3", MagicMock()
    ):
        yield


@pytest.fixture()
async def matrix(workspace, published_form, outside_services, fake_dns):
    workspace.is_pro = True
    await container.workspace_repo().save(workspace)
    members = container.workspace_user_repo()
    for user, roles, disabled in (
        (admin_user, [WorkspaceRoles.ADMIN], False),
        (disabled_user, [WorkspaceRoles.ADMIN], True),
        (removable_user, [WorkspaceRoles.COLLABORATOR], False),
    ):
        await members.save(
            WorkspaceUserDocument(
                workspace_id=workspace.id,
                user_id=user.id,
                roles=roles,
                disabled=disabled,
            )
        )
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponse(**formResponse),
        testUser2,
    )
    group = await container.responder_groups_service().create_group(
        workspace.id, "Matrix", ["a@example.com"], testUser, None, "", None
    )
    api_key = await container.api_key_service().create_key(
        workspace.id, CreateAPIKeyDto(name="matrix", scopes=["forms:read"]), testUser
    )
    workspace_form = await container.workspace_form_repo().find_workspace_form(
        workspace.id, published_form.form_id
    )
    media = await container.media_library_repo().add_media_in_workspace_library(
        workspace_id=str(workspace.id),
        media_url="https://s3/media_library/abc",
        media_type="IMAGE",
        media_name="logo.png",
        s3_key="abc",
    )
    template = await container.workspace_form_service().duplicate_form(
        workspace.id, published_form.form_id, testUser, is_template=True
    )
    form_import = await container.form_import_repo().save(
        FormImportDocument(
            id=PydanticObjectId(),
            workspace_id=workspace.id,
            form_id=published_form.form_id,
            created_by=testUser.id,
            file_name="form.pdf",
            content_type="application/pdf",
            size_bytes=1,
            sha256="0" * 64,
            source_key="private/x/form.pdf",
        )
    )
    action = await container.action_repository().create_global_action(
        ActionDto(name="matrix_action", action_code="", type="external"), testUser
    )
    invitation = (
        await container.workspace_invitation_repo().create_workspace_invitation(
            workspace_id=workspace.id,
            invitation=InvitationRequest(
                email="pending@example.com", role=WorkspaceRoles.COLLABORATOR
            ),
        )
    )
    domain = await container.workspace_domain_repo().create(
        WorkspaceDomainDocument(
            id=PydanticObjectId(),
            workspace_id=workspace.id,
            domain="matrix-domain.org",
            verification_token="0" * 32,
            created_by=testUser.id,
        )
    )
    other_domain = await container.workspace_domain_repo().create(
        WorkspaceDomainDocument(
            id=PydanticObjectId(),
            workspace_id=PydanticObjectId(),
            domain="matrix-elsewhere.org",
            verification_token="1" * 32,
            created_by=testUser1.id,
        )
    )
    return {
        "ws": str(workspace.id),
        "domain": str(domain.id),
        "other_domain": str(other_domain.id),
        "name": workspace.workspace_name,
        "form": published_form.form_id,
        "slug": workspace_form.settings.custom_url,
        "response": response.response_id,
        "group": str(group.id),
        "removable": removable_user.id,
        "api_key": api_key.id,
        "media": str(media.media_id),
        "template": str(template.id),
        "import": str(form_import.id),
        "action": str(action.id),
        "invitation": invitation.invitation_token,
        "random": _oid(),
    }


def _cookies(user: User) -> dict:
    token = container.jwt_service().encode(user)
    return {"Authorization": token, "RefreshToken": token}


def _body(response):
    try:
        return response.json()
    except ValueError:
        return response.text


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("case", CASES, ids=[case.name for case in CASES])
async def test_permission_matrix(
    client: AsyncClient, matrix, monkeypatch, case: Case, role: str
):
    fake = None
    if case.ai_replies is not None:
        fake = FakeProvider()
        fake.replies = list(case.ai_replies)
        use_fake_provider(monkeypatch, fake)
        workspace = await container.workspace_repo().find_by_id(
            PydanticObjectId(matrix["ws"])
        )
        await enable_ai(workspace)
        # allows insights on the form, then answers it with real questions
        await _seed_form_and_responses(workspace.id, matrix["form"])

    request = case.request(matrix)
    response = await client.request(
        case.method,
        case.path.format(**matrix),
        cookies=_cookies(USERS[role]),
        **request,
    )
    seen = f"{case.name} as {role}: {response.status_code} {response.text}"
    refused = response.status_code == 403 and _body(response) == case.refused_body
    if role in case.allowed:
        assert not refused, f"{role} was refused {case.name}"
        if response.status_code == 403:
            assert case.allowed_403 and case.allowed_403 in response.text, seen
        assert response.status_code < 500 or response.status_code == 503, seen
        if case.ok is not None:
            assert response.status_code == case.ok, seen
        if fake is not None:
            assert fake.calls, seen
    else:
        assert refused, f"{role} was not refused: {seen}"
        if fake is not None:
            assert fake.calls == [], seen


EXPECTED_PERMISSIONS = {
    OWNER: ALL_PERMISSIONS,
    ADMIN: ALL_PERMISSIONS - {Permission.WORKSPACE_BILLING},
    COLLABORATOR: MEMBER_PERMISSIONS,
    NON_MEMBER: frozenset(),
    DISABLED: frozenset(),
}


@pytest.mark.parametrize("role", ROLES)
async def test_effective_permissions_endpoint(client: AsyncClient, matrix, role: str):
    response = await client.get(
        f"/api/v1/workspaces/{matrix['ws']}/permissions",
        cookies=_cookies(USERS[role]),
    )

    assert response.status_code == 200, response.text
    assert set(response.json()["permissions"]) == {
        p.value for p in EXPECTED_PERMISSIONS[role]
    }


async def test_effective_permissions_need_a_signed_in_user(client: AsyncClient, matrix):
    response = await client.get(f"/api/v1/workspaces/{matrix['ws']}/permissions")
    assert response.status_code == 401


# What the owner of a disabled workspace still reaches, and what members don't.
DISABLED_WORKSPACE_READS = (
    W + "/forms",
    F + "/submissions",
    F + "/submissions?request_for_deletion=true",
    W + "/all-submissions?request_for_deletion=true",
    W + "/responders",
    W + "/stats",
)
DISABLED_WORKSPACE_CHANGES = (
    ("POST", W + "/forms", {"data": {"form_body": json.dumps(formData)}}),
    ("PATCH", F + "/settings", {"json": {"pinned": True}}),
    ("GET", W + "/members", {}),
    ("PUT", W + "/ai-settings", {"json": {"enabled": False}}),
)


async def test_a_disabled_workspace_leaves_its_owner_read_and_privacy(
    client: AsyncClient, matrix
):
    """A downgraded owner still answers deletion requests and reaches their
    respondents' data (GDPR), and changes nothing else; other members get
    nothing."""
    workspace = await container.workspace_repo().find_by_id(
        PydanticObjectId(matrix["ws"])
    )
    workspace.disabled = True
    await container.workspace_repo().save(workspace)
    authorization = container.authorization_service()
    assert (
        await authorization.effective_permissions(testUser, matrix["ws"])
        == DISABLED_WORKSPACE_OWNER_PERMISSIONS
    )
    for role in (ADMIN, COLLABORATOR):
        assert not await authorization.effective_permissions(USERS[role], matrix["ws"])

    for path in DISABLED_WORKSPACE_READS:
        url = path.format(**matrix)
        owner = await client.get(url, cookies=_cookies(testUser))
        assert owner.status_code == 200, (url, owner.text)
        for role in (ADMIN, COLLABORATOR):
            member = await client.get(url, cookies=_cookies(USERS[role]))
            assert member.status_code == 403, (role, url)

    for method, path, request in DISABLED_WORKSPACE_CHANGES:
        refused = await client.request(
            method, path.format(**matrix), cookies=_cookies(testUser), **request
        )
        assert refused.status_code == 403, (method, path, refused.text)


def test_every_case_is_named_once():
    names = [case.name for case in CASES]
    assert len(names) == len(set(names))
