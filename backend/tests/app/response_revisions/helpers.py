"""Shared set-up of the response revision tests: a published page-based form
that lets respondents edit, a response from a respondent, members with roles,
and the calls a staff member makes."""

import json
from typing import Any, Dict, Optional

from common.models.user import User

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser2

API = "/api/v1"
STAFF = testUser  # the workspace owner
RESPONDENT = testUser2  # not a member; edits their own response


def question(field_id: str, qtype: str = "short_text", title: Optional[str] = None, **extra):
    field = {"id": field_id, "type": qtype, "title": title or field_id}
    props = extra.pop("properties", None)
    if props:
        field["properties"] = props
    if extra:
        field.update(extra)
    return field


NAME = question("name", title="Your name", validations={"required": True})
AGE = question("age", "number", title="Age", validations={"min_value": 0, "max_value": 120})
CITY = question("city", title="City")
NOTE = question("note", "long_text", title="Note")
COLOUR = question(
    "colour",
    "dropdown",
    title="Colour",
    properties={"choices": [{"id": "red", "value": "Red"}, {"id": "blue", "value": "Blue"}]},
)
DEFAULT_QUESTIONS = [NAME, AGE, CITY, NOTE, COLOUR]


def text(value: str) -> Dict[str, Any]:
    return {"type": "text", "text": value}


def number(value: float) -> Dict[str, Any]:
    return {"type": "number", "number": value}


def choice(choice_id: str) -> Dict[str, Any]:
    return {"type": "choice", "choice": {"value": choice_id}}


def cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def make_member(workspace, user: User, roles) -> None:
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=roles)
    )


async def published_form(workspace, questions=None, **settings_changes):
    """A published page-based form whose respondents (verified) may edit."""
    from common.models.standard_form import StandardForm

    service = container.workspace_form_service()
    form = StandardForm(
        builder_version="v2",
        title="Quarterly survey",
        fields=[
            {
                "id": "page-1",
                "type": "slide",
                "index": 0,
                "properties": {"fields": questions or DEFAULT_QUESTIONS},
            }
        ],
    )
    created = await service.create_form(workspace.id, form, STAFF)
    await service.publish_form(workspace.id, created.form_id, STAFF)
    association = await container.workspace_form_repo().find_workspace_form(
        workspace.id, str(created.form_id)
    )
    association.settings.require_verified_identity = True
    association.settings.allow_editing_response = True
    for key, value in settings_changes.items():
        setattr(association.settings, key, value)
    await container.workspace_form_repo().save(association)
    return created


async def submit(workspace, form, answers: Dict[str, Any], user: User = RESPONDENT):
    """A submission, carrying the version the page reported (the webapp
    sends ``form_version``; the server does not set it)."""
    latest = await container.form_repo().get_latest_version_of_form(form.form_id)
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers=answers, form_version=latest.version if latest else None
        ),
        user,
    )


async def respondent_edit(workspace, form, response, answers, user: User = RESPONDENT):
    return await container.workspace_form_service().patch_response(
        workspace.id,
        form.form_id,
        response.response_id,
        None,
        StandardFormResponseCamelModel(answers=answers),
        user,
    )


def answers_url(workspace, form, response) -> str:
    return (
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}"
        f"/submissions/{response.response_id}/answers"
    )


def revisions_url(workspace, form, response, seq: Optional[int] = None) -> str:
    base = (
        f"{API}/workspaces/{workspace.id}/forms/{form.form_id}"
        f"/submissions/{response.response_id}/revisions"
    )
    return base if seq is None else f"{base}/{seq}"


async def stored_answers(workspace, response) -> Dict[str, Any]:
    """The decrypted answers as stored now."""
    service = container.form_response_service()
    row = await service.workspace_response(workspace.id, response.response_id)
    return dict(
        service.decrypt_form_response(
            workspace_id=workspace.id, response=row.model_copy(deep=True)
        ).answers
    )


async def revision_rows(response) -> list:
    """The revision log entries of a response, oldest first."""
    stored = await container.form_response_repo().get_response(response.response_id)
    return await container.response_revision_repo().list_for_response(stored.id)
