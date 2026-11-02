"""Review fixes of the versions page: the version a submission carries is the
server's, the publisher's id never reaches the action executor, and a version
in a request is parsed strictly (never a 500)."""

import pytest
from common.models.standard_form import ThankYouPageField, WelcomePageField

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


# -- restore holds an old version to today's save checks ---------------------------------


async def _publish_unchecked(form, mutate):
    """A version that holds what a save would refuse: made through the
    repositories (as a version published before a check existed was)."""
    service = container.form_service()
    draft = await service.get_form_document_by_id(str(form.form.form_id))
    mutate(draft)
    await container.form_repo().save_form(draft)
    await service.publish_form(form.form.form_id)
    await form.save([_q("a", "Name"), _q("c", "Email")], title="Clean again")


def _ending(link):
    return lambda d: setattr(
        d,
        "thankyou_page",
        [ThankYouPageField(id="e1", isDefault=True, title="Bye", buttonLink=link, buttonText="Go")],
    )


class TestRestoreIsHeldToTheChecksOfASave:
    async def test_a_third_party_image_is_refused_like_a_save_refuses_it(self, two_versions):
        form = two_versions

        def mutate(draft):
            draft.welcome_page = WelcomePageField(
                title="Hi", imageUrl="https://tracker.example.test/pixel.png"
            )

        await _publish_unchecked(form, mutate)
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        refused = await form.restore(3, stamp, replace=True)
        assert refused.status_code == 422, refused.text
        assert "tracker.example.test" not in (await form.draft()).model_dump_json()
        # the same value through a save is refused the same way
        service = container.workspace_form_service()
        from common.models.standard_form import StandardForm
        from backend.app.exceptions import HTTPException

        bad = StandardForm(**(await form.draft()).model_dump())
        bad.welcome_page = WelcomePageField(
            title="Hi", imageUrl="https://tracker.example.test/pixel.png"
        )
        with pytest.raises(HTTPException) as error:
            await service.update_form(form.workspace.id, form.form.form_id, bad, testUser)
        assert error.value.status_code == 422

    async def test_a_link_that_is_not_http_is_refused(self, two_versions):
        form = two_versions
        await _publish_unchecked(form, _ending("javascript:alert(1)"))
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        refused = await form.restore(3, stamp, replace=True)
        assert refused.status_code == 422, refused.text
        draft = await form.draft()
        assert "javascript:" not in draft.model_dump_json()

    async def test_a_clean_version_still_restores(self, two_versions):
        form = two_versions
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        assert (await form.restore(1, stamp, replace=True)).status_code == 200

    async def test_a_link_the_draft_already_holds_is_kept_like_a_save_keeps_it(
        self, two_versions
    ):
        form = two_versions
        await _publish_unchecked(form, _ending("javascript:alert(1)"))
        # the draft holds the same stored link: a save that sends it back is no change
        draft = await form.draft()
        draft.thankyou_page = [
            ThankYouPageField(id="e1", isDefault=True, title="Bye", buttonLink="javascript:alert(1)", buttonText="Go")
        ]
        await container.form_repo().save_form(draft)
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        ok = await form.restore(3, stamp, replace=True)
        assert ok.status_code == 200, ok.text
        # kept as is (the save's rule), not made safe by restore alone
        assert (await form.draft()).thankyou_page is not None


class TestUpdateFormBehavesAsBefore:
    async def test_the_checks_a_save_runs_still_refuse_what_they_refused(self, two_versions):
        from backend.app.exceptions import HTTPException
        from common.models.standard_form import StandardForm

        form = two_versions
        service = container.workspace_form_service()
        base = StandardForm(**(await form.draft()).model_dump())

        async def save(change):
            candidate = base.model_copy(deep=True)
            change(candidate)
            return await service.update_form(
                form.workspace.id, form.form.form_id, candidate, testUser
            )

        def link(candidate):
            candidate.thankyou_page = [
                ThankYouPageField(id="e1", isDefault=True, title="x", buttonLink="javascript:x")
            ]

        def image(candidate):
            candidate.welcome_page = WelcomePageField(
                title="x", imageUrl="https://tracker.example.test/p.png"
            )

        for change in (link, image):
            with pytest.raises(HTTPException) as error:
                await save(change)
            assert error.value.status_code == 422
        # a clean save goes through, and keeps working with the drop lists
        dropped_rules, dropped_logic = [], []
        candidate = base.model_copy(deep=True)
        await service.update_form(
            form.workspace.id,
            form.form.form_id,
            candidate,
            testUser,
            dropped_rules=dropped_rules,
            dropped_option_logic=dropped_logic,
        )
        assert dropped_rules == [] and dropped_logic == []
