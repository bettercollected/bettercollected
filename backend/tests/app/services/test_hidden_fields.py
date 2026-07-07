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
