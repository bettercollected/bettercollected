import json

from common.models.standard_form import StandardForm, StandardFormResponse

from backend.app.container import container
from backend.app.schemas.standard_form_response import FormResponseDocument


async def test_submitted_hidden_fields_are_encrypted_at_rest_and_decrypted_on_read(
    workspace, workspace_form
):
    hidden = {"utm_source": "newsletter", "name": "Ada"}
    response = await container.form_response_service().submit_form_response(
        workspace_form.form_id,
        StandardFormResponse(answers={}, hidden_fields=hidden),
        workspace.id,
    )

    # The service returns the decrypted view for the caller...
    assert response.hidden_fields == hidden

    # ...but at rest the values are an encrypted blob, like answers.
    stored = await FormResponseDocument.find_one(
        {"response_id": response.response_id}
    )
    assert isinstance(stored.hidden_fields, (bytes, str))
    assert json.dumps(hidden) != stored.hidden_fields

    decrypted = container.form_response_service().decrypt_form_response(
        workspace_id=workspace.id, response=stored
    )
    assert decrypted.hidden_fields == hidden


async def test_submission_without_hidden_fields_stays_none(workspace, workspace_form):
    response = await container.form_response_service().submit_form_response(
        workspace_form.form_id,
        StandardFormResponse(answers={}),
        workspace.id,
    )
    stored = await FormResponseDocument.find_one(
        {"response_id": response.response_id}
    )
    assert stored.hidden_fields is None


async def test_update_form_persists_declared_hidden_fields(workspace, workspace_form):
    form = StandardForm(**workspace_form.model_dump(mode="json"))
    form.hidden_fields = ["utm_source", "utm_medium"]

    updated = await container.form_service().update_form(
        form_id=workspace_form.form_id, form=form
    )
    assert updated.hidden_fields == ["utm_source", "utm_medium"]

    # A PATCH that omits hidden_fields (e.g. an older webapp bundle) must not
    # wipe them — only an explicit empty list clears.
    form.hidden_fields = None
    preserved = await container.form_service().update_form(
        form_id=workspace_form.form_id, form=form
    )
    assert preserved.hidden_fields == ["utm_source", "utm_medium"]

    form.hidden_fields = []
    cleared = await container.form_service().update_form(
        form_id=workspace_form.form_id, form=form
    )
    assert cleared.hidden_fields == []


async def test_changing_hidden_fields_marks_form_as_updated(workspace, workspace_form):
    form_service = container.form_service()
    published = await form_service.publish_form(workspace_form.form_id)

    # No changes since publishing -> not "updated".
    current = await form_service.get_form_document_by_id(str(workspace_form.form_id))
    assert form_service.has_form_been_updated(current, published) is False

    current.hidden_fields = ["utm_source"]
    assert form_service.has_form_been_updated(current, published) is True


async def test_anonymize_is_enforced_server_side(workspace, published_form):
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
    from tests.app.controllers.data import testUser

    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=True),
        testUser,
    )

    stored = await FormResponseDocument.find_one(
        {"response_id": response.response_id}
    )
    # The anonymity choice must hold at rest: no owner identifier, no email —
    # only the one-way hash that lets the responder find their own submission.
    assert stored.dataOwnerIdentifier is None
    assert stored.respondent_email is None
    assert stored.anonymous_identity is not None
    assert stored.anonymous_identity != testUser.sub


async def test_identity_is_kept_when_not_anonymized(workspace, published_form):
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
    from tests.app.controllers.data import testUser

    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=False),
        testUser,
    )

    stored = await FormResponseDocument.find_one(
        {"response_id": response.response_id}
    )
    assert stored.dataOwnerIdentifier == testUser.sub


async def test_trust_layer_settings_patch_roundtrip(workspace, workspace_form):
    from backend.app.models.dtos.settings_patch import SettingsPatchDto
    from tests.app.controllers.data import testUser

    patched = await container.form_service().patch_settings_in_workspace_form(
        workspace.id,
        workspace_form.form_id,
        SettingsPatchDto(
            purpose="To schedule your appointment",
            retention_text="kept for 90 days",
            privacy_policy_url="https://example.com/privacy",
        ),
        testUser,
    )
    assert patched.settings.purpose == "To schedule your appointment"
    assert patched.settings.retention_text == "kept for 90 days"
    assert patched.settings.privacy_policy_url == "https://example.com/privacy"

    # Empty string clears; omitted fields are preserved.
    cleared = await container.form_service().patch_settings_in_workspace_form(
        workspace.id,
        workspace_form.form_id,
        SettingsPatchDto(purpose=""),
        testUser,
    )
    assert cleared.settings.purpose is None
    assert cleared.settings.retention_text == "kept for 90 days"


async def test_anonymous_owner_can_request_deletion(workspace, published_form):
    """The deletion right must survive anonymity: an anonymous response has no
    dataOwnerIdentifier, so the owner is recognisable only through the
    anonymous identity hash. Before the fix, non-admin anonymous responders
    were 403'd out of deleting their own response, and the created request
    carried no identity at all — it could never be listed back to them."""
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
    from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
    from tests.app.controllers.data import testUser2

    # testUser2 is not a member of the workspace — pure responder.
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=True),
        testUser2,
    )

    await container.form_response_service().request_for_response_deletion(
        workspace.id, response.response_id, testUser2
    )

    stored_response = await FormResponseDocument.find_one(
        {"response_id": response.response_id}
    )
    request = await FormResponseDeletionRequest.find_one(
        {"response_id": response.response_id}
    )
    assert request is not None
    # Attribution survives: the request carries the same anonymous hash the
    # submissions listing matches on.
    assert request.anonymous_identity == stored_response.anonymous_identity
    assert request.dataOwnerIdentifier is None


async def test_anonymous_submissions_are_not_listed_under_the_account(
    workspace, published_form
):
    """Anonymity has to mean something at the account level: verifying your
    email must not link anonymous submissions back to you in the portal
    listing. The submission number (receipt) is the only key to an anonymous
    response — exactly what the portal copy promises responders."""
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
    from tests.app.controllers.data import testUser2

    identified = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=False),
        testUser2,
    )
    anonymous = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponseCamelModel(answers={}, anonymize=True),
        testUser2,
    )

    from fastapi_pagination import Page, Params
    from fastapi_pagination.api import set_page, set_params

    # In the app these come from the route context (response_model +
    # add_pagination); set them explicitly for a direct service call.
    set_page(Page[StandardFormResponseCamelModel])
    set_params(Params(page=1, size=50))
    page = await container.form_response_service().get_user_submissions(
        workspace.id, testUser2
    )
    listed_ids = [item.response_id for item in page.items]
    assert identified.response_id in listed_ids
    assert anonymous.response_id not in listed_ids
