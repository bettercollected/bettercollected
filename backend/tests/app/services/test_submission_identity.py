"""Who submitted a response comes only from the signed-in user, never from
the submission body, and a form that requires a verified identity refuses
submissions without one. Respondent feedback notices go to that identity,
so a body naming someone else must not stick."""

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from tests.app.controllers.data import testUser

VICTIM = "someone-else@example.com"


async def _submit(workspace, form, user, **fields):
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={}, **fields),
        user,
    )
    return await container.form_response_repo().get_response(response.response_id)


async def _require_identity(workspace, form):
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
    )
    workspace_form.settings.require_verified_identity = True
    await container.workspace_form_repo().save(workspace_form)


async def test_a_signed_in_submission_cannot_name_someone_else(
    workspace, published_form
):
    stored = await _submit(
        workspace, published_form, testUser, dataOwnerIdentifier=VICTIM
    )
    assert stored.dataOwnerIdentifier == testUser.sub


async def test_an_anonymous_submission_cannot_name_anyone(workspace, published_form):
    stored = await _submit(workspace, published_form, None, dataOwnerIdentifier=VICTIM)
    assert stored.dataOwnerIdentifier is None


async def test_the_anonymous_hash_is_never_taken_from_the_body(
    workspace, published_form
):
    stored = await _submit(
        workspace,
        published_form,
        None,
        anonymize=True,
        anonymous_identity="forged-hash",
    )
    assert stored.anonymous_identity is None


async def test_a_form_requiring_identity_refuses_anonymous_submissions(
    workspace, published_form
):
    await _require_identity(workspace, published_form)
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, published_form, None)
    assert error.value.status_code == 401

    stored = await _submit(workspace, published_form, testUser)
    assert stored.dataOwnerIdentifier == testUser.sub
