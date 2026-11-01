"""Review fixes of the versions page: the version a submission carries is the
server's, the publisher's id never reaches the action executor, and a version
in a request is parsed strictly (never a 500)."""

import pytest

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.services import form_versions
from backend.app.services.form_versions import service as versions_service
from backend.app.services.internal_fields import strip_internal_fields
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1, testUser2
from tests.app.form_versions.test_versions_api import Form, _q  # noqa: F401
from tests.app.form_versions.test_versions_api import (  # noqa: F401
    form,
    no_member_names,
    switched_on,
    two_versions,
)

pytestmark = pytest.mark.asyncio


class TestSubmissionVersionIsTheServers:
    async def test_a_version_sent_by_the_respondent_is_ignored(self, two_versions):
        form = two_versions
        for claimed in (1, 99, None):
            stored = await container.workspace_form_service().submit_response(
                form.workspace.id,
                form.form.form_id,
                StandardFormResponseCamelModel(
                    answers={"a": {"type": "text", "text": "x"}}, form_version=claimed
                ),
                testUser2,
            )
            row = await container.form_response_repo().get_response(
                stored.response_id
            )
            # the published version the answers were checked against: the latest
            assert row.form_version == 2


class TestPublisherNeverReachesTheExecutor:
    async def test_strip_internal_fields_clears_it(self):
        version = FormVersionsDocument(
            form_id="f", version=2, title="T", published_by="6" * 24
        )
        scrubbed = strip_internal_fields(version.model_copy(deep=True))
        assert scrubbed.published_by is None
        assert "6" * 24 not in scrubbed.model_dump_json()
        # the stored document is untouched (the copy is scrubbed)
        assert version.published_by == "6" * 24


class TestVersionParameters:
    async def test_a_superscript_or_huge_number_is_422_not_500(self, two_versions):
        for bad in ("²", "٣", "1_0", "-1", "0", "1e3", " ", "9999999999999999999999"):
            response = await two_versions.diff(bad, "draft")
            assert response.status_code == 422, (bad, response.text)
            assert response.json()["code"] == "invalid_version"
            response = await two_versions.diff("1", bad)
            assert response.status_code == 422, (bad, response.text)

    async def test_the_largest_version_is_a_404_not_an_error(self, two_versions):
        response = await two_versions.diff(str(versions_service.MAX_VERSION), "draft")
        assert response.status_code == 404
        assert (
            await two_versions.diff(str(versions_service.MAX_VERSION + 1), "draft")
        ).status_code == 422

    async def test_a_restore_of_a_version_beyond_any_is_404_after_authorizing(
        self, two_versions, client
    ):
        stamp = (await two_versions.versions()).json()["draft"]["updatedAt"]
        for number in (10**30, versions_service.MAX_VERSION + 1, 0, -5):
            response = await two_versions.restore(number, stamp)
            assert response.status_code == 404, (number, response.text)
        # a caller without form.edit learns nothing: 403 first
        outsider = {"Authorization": access_token(testUser1), "RefreshToken": access_token(testUser1)}
        refused = await two_versions.restore(10**30, stamp, cookies=outsider)
        assert refused.status_code == 403

    async def test_a_bad_version_to_a_non_member_is_403_not_422(self, two_versions):
        outsider = {"Authorization": access_token(testUser1), "RefreshToken": access_token(testUser1)}
        refused = await two_versions.diff("²", "draft", cookies=outsider)
        assert refused.status_code == 403


class TestListIsCappedAndSaysSo:
    async def test_older_versions_beyond_the_limit_set_truncated(
        self, two_versions, monkeypatch
    ):
        monkeypatch.setattr(versions_service, "LIST_LIMIT", 1)
        body = (await two_versions.versions()).json()
        assert [v["version"] for v in body["versions"]] == [2]
        assert body["truncated"] is True
        monkeypatch.setattr(versions_service, "LIST_LIMIT", 5)
        body = (await two_versions.versions()).json()
        assert len(body["versions"]) == 2 and body["truncated"] is False
