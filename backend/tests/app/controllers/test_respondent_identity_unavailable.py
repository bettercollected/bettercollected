"""While this process cannot trust its respondent identity key (it is known to
differ from the stored one, or it is not verified against the stored key check),
everything that needs an identity answers 503 with a fixed body and Retry-After,
and never falls back to another identity or stores a file."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.utils import respondent_identity as identity
from backend.app.utils.respondent_identity import fingerprint_of, key_check_value
from tests.app.controllers.data import testUser1
from tests.app.controllers.test_respondent_deletion_requests import (  # noqa: F401
    _cookies,
    _submit,
    _url,
)
from tests.app.controllers.test_responses_per_workspace import _no_auth_service  # noqa: F401


def _break(monkeypatch, state: str) -> None:
    monkeypatch.setattr(identity, "_key_mismatch_seen", [state == "mismatch"])
    monkeypatch.setattr(identity, "_key_verified", [False])


def _assert_unavailable(response) -> None:
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": identity.UNAVAILABLE_DETAIL}
    assert response.headers["retry-after"] == str(identity.RETRY_AFTER_SECONDS)


@pytest.fixture
def fingerprint() -> str:
    return fingerprint_of(key_check_value(identity.configured_key()))


@pytest.mark.parametrize("state", ["mismatch", "unverified"])
async def test_the_identity_paths_answer_503_and_nothing_else_changes(
    client: AsyncClient, workspace, published_form, fingerprint, monkeypatch, state
):
    # an anonymous response made while the key was fine
    mine = await _submit(workspace, published_form, testUser1, anonymize=True)
    _break(monkeypatch, state)

    def body_of(args):
        return {"response": json.dumps(args)}

    # a new anonymous submission is refused: no identity, no fallback to the address
    refused = await client.post(
        f"{_url(workspace)}/forms/{published_form.form_id}/response",
        data=body_of({"answers": {}, "anonymize": True}),
        cookies=_cookies(testUser1),
    )
    _assert_unavailable(refused)
    assert fingerprint not in refused.text and "v2:" not in refused.text

    # the respondent's own deletion requests and the view / deletion of their response
    listed = await client.get(
        f"{_url(workspace)}/submissions",
        params={"request_for_deletion": True},
        cookies=_cookies(testUser1),
    )
    _assert_unavailable(listed)
    deleted = await client.delete(
        f"{_url(workspace)}/submissions/{mine.response_id}", cookies=_cookies(testUser1)
    )
    _assert_unavailable(deleted)
    viewed = await client.get(
        f"{_url(workspace)}/submissions/{mine.response_id}", cookies=_cookies(testUser1)
    )
    _assert_unavailable(viewed)

    # what needs no identity keeps working
    plain = await client.post(
        f"{_url(workspace)}/forms/{published_form.form_id}/response",
        data=body_of({"answers": {}, "anonymize": False}),
        cookies=_cookies(testUser1),
    )
    assert plain.status_code == 200, plain.text
    own = await client.get(
        f"{_url(workspace)}/submissions", cookies=_cookies(testUser1)
    )
    assert own.status_code == 200, own.text


async def test_a_refused_anonymous_submission_uploads_nothing(
    workspace, published_form, monkeypatch
):
    """The identity is computed before the upload block: no orphan object."""
    _break(monkeypatch, "unverified")
    with patch.object(
        WorkspaceFormService, "upload_files_to_s3_and_update_url", new=AsyncMock()
    ) as upload:
        with pytest.raises(identity.IdentityKeyError):
            await container.workspace_form_service().submit_response(
                workspace.id,
                published_form.form_id,
                StandardFormResponseCamelModel(answers={}, anonymize=True),
                testUser1,
                form_files=[object()],
            )
    upload.assert_not_called()
