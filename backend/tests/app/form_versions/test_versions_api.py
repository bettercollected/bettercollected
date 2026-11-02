"""The versions routes of a form (list, compare, restore) behind
``FORM_REVISIONS_UI_ENABLED``: the switch, the permissions, what each answers
and that restoring changes only the draft."""

import json

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services.form_versions.mode import DISABLED_CODE
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser

pytestmark = pytest.mark.asyncio

API = "/api/v1"


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    monkeypatch.setattr(settings, "FORM_REVISIONS_UI_ENABLED", True)


@pytest.fixture(autouse=True)
def no_member_names(monkeypatch):
    """The auth service is not there: names are best effort and absent."""

    async def get(self, url, **kwargs):
        raise ConnectionError("no auth service in tests")

    monkeypatch.setattr(type(container.http_client()), "get", get)


def _q(field_id, title=None, **extra):
    return {"id": field_id, "type": "short_text", "title": title or field_id, **extra}


def _body(fields, title="Versions"):
    return {
        "title": title,
        "builderVersion": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {"fields": fields},
            }
        ],
    }


class Form:
    """A form of the test workspace with a page-based draft."""

    def __init__(self, workspace, form, cookies, client):
        self.workspace, self.form, self.cookies, self.client = (
            workspace,
            form,
            cookies,
            client,
        )
        self.base = f"{API}/workspaces/{workspace.id}/forms/{form.form_id}"

    async def save(self, fields, title="Versions", expected=None):
        data = {"form_body": json.dumps(_body(fields, title))}
        if expected:
            data["expected_updated_at"] = expected
        response = await self.client.patch(self.base, cookies=self.cookies, data=data)
        assert response.status_code == 200, response.text
        return response.json()["updatedAt"]

    async def publish(self):
        response = await self.client.post(
            f"{self.base}/publish", cookies=self.cookies
        )
        assert response.status_code == 200, response.text
        return response

    async def versions(self, cookies=None):
        return await self.client.get(
            f"{self.base}/versions", cookies=cookies or self.cookies
        )

    async def diff(self, a, b, cookies=None):
        return await self.client.get(
            f"{self.base}/version-diff",
            params={"from": a, "to": b},
            cookies=cookies or self.cookies,
        )

    async def restore(self, version, expected, replace=False, cookies=None):
        return await self.client.post(
            f"{self.base}/versions/{version}/restore",
            json={"expectedUpdatedAt": expected, "replaceDraft": replace},
            cookies=cookies or self.cookies,
        )

    async def draft(self):
        return await container.form_service().get_form_document_by_id(
            str(self.form.form_id)
        )


@pytest.fixture()
async def form(client, workspace, workspace_form, test_user_cookies):
    return Form(workspace, workspace_form, test_user_cookies, client)


@pytest.fixture()
async def two_versions(form):
    """v1: a and b; v2: a renamed, b gone, c added. The draft is then v2."""
    await form.save([_q("a", "Name"), _q("b", "Phone")], title="One")
    await form.publish()
    await form.save([_q("a", "Full name"), _q("c", "Email")], title="Two")
    await form.publish()
    return form


class TestSwitch:
    async def test_off_every_route_is_refused_with_the_code(
        self, two_versions, monkeypatch
    ):
        monkeypatch.setattr(settings, "FORM_REVISIONS_UI_ENABLED", False)
        form = two_versions
        for response in (
            await form.versions(),
            await form.diff("1", "2"),
            await form.restore(1, "2030-01-01T00:00:00Z"),
        ):
            assert response.status_code == 422, response.text
            assert response.json()["code"] == DISABLED_CODE

    async def test_off_the_single_version_read_still_works(
        self, two_versions, monkeypatch, client, test_user_cookies
    ):
        monkeypatch.setattr(settings, "FORM_REVISIONS_UI_ENABLED", False)
        response = await client.get(
            f"{two_versions.base}/versions/1", cookies=test_user_cookies
        )
        assert response.status_code == 200
        assert response.json()["title"] == "One"

    async def test_the_permissions_answer_carries_the_switch(
        self, client, workspace, test_user_cookies, monkeypatch
    ):
        url = f"{API}/workspaces/{workspace.id}/permissions"
        on = await client.get(url, cookies=test_user_cookies)
        assert on.json()["formRevisionsUiEnabled"] is True
        monkeypatch.setattr(settings, "FORM_REVISIONS_UI_ENABLED", False)
        off = await client.get(url, cookies=test_user_cookies)
        assert off.json()["formRevisionsUiEnabled"] is False


class TestList:
    async def test_lists_newest_first_with_who_and_current(self, two_versions):
        response = await two_versions.versions()
        assert response.status_code == 200, response.text
        body = response.json()
        assert [v["version"] for v in body["versions"]] == [2, 1]
        assert [v["current"] for v in body["versions"]] == [True, False]
        newest = body["versions"][0]
        assert newest["publishedAt"]
        # the owner publishes; their role is known, the name lookup is down
        assert newest["publishedBy"]["role"]
        assert newest["publishedBy"]["former"] is False
        # an id never leaves
        assert str(testUser.id) not in response.text

    async def test_the_draft_state(self, two_versions):
        form = two_versions
        draft = (await form.versions()).json()["draft"]
        assert draft["hasUnpublishedChanges"] is False and draft["updatedAt"]
        await form.save([_q("a", "Full name"), _q("c", "Email"), _q("d", "New")], title="Two")
        draft = (await form.versions()).json()["draft"]
        assert draft["hasUnpublishedChanges"] is True

    async def test_a_version_published_by_someone_who_left_is_a_former_member(
        self, two_versions
    ):
        from backend.app.schemas.form_versions import FormVersionsDocument

        repo = container.form_repo()
        latest = await repo.get_latest_version_of_form(two_versions.form.form_id)
        latest.published_by = "6" * 24  # not a member of the workspace
        await repo.save_form_version(latest)
        newest = (await two_versions.versions()).json()["versions"][0]
        assert newest["publishedBy"] == {"name": None, "role": None, "former": True}
        assert "6" * 24 not in json.dumps(newest)

    async def test_a_version_without_an_author_has_none(self, two_versions):
        repo = container.form_repo()
        first = await repo.get_form_by_by_version(two_versions.form.form_id, 1)
        first.published_by = None
        await repo.save_form_version(first)
        oldest = (await two_versions.versions()).json()["versions"][1]
        assert oldest["publishedBy"] is None


class TestCompare:
    async def test_two_versions_as_coded_entries(self, two_versions):
        response = await two_versions.diff("1", "2")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["fromVersion"] == "1" and body["toVersion"] == "2"
        assert body["changed"] is True
        by_kind = {}
        for entry in body["entries"]:
            by_kind.setdefault(entry["kind"], []).append(entry)
        assert by_kind["form_title_changed"][0]["params"] == {
            "before": "One",
            "after": "Two",
        }
        assert by_kind["title_changed"][0]["ref"] == "a"
        assert by_kind["question_added"][0]["ref"] == "c"
        assert by_kind["question_removed"][0]["ref"] == "b"

    async def test_the_other_direction_swaps_added_and_removed(self, two_versions):
        body = (await two_versions.diff("2", "1")).json()
        kinds = {(e["kind"], e["ref"]) for e in body["entries"]}
        assert ("question_added", "b") in kinds and ("question_removed", "c") in kinds

    async def test_the_draft_is_a_side(self, two_versions):
        form = two_versions
        same = (await form.diff("2", "draft")).json()
        assert same["changed"] is False and same["entries"] == []
        await form.save([_q("a", "Full name"), _q("c", "Email"), _q("d", "New")], title="Two")
        body = (await form.diff("2", "draft")).json()
        assert [(e["kind"], e["ref"]) for e in body["entries"]] == [
            ("question_added", "d")
        ]

    async def test_a_version_that_does_not_exist_is_404(self, two_versions):
        assert (await two_versions.diff("1", "9")).status_code == 404

    async def test_a_bad_side_is_422(self, two_versions):
        response = await two_versions.diff("one", "2")
        assert response.status_code == 422
        assert response.json()["code"] == "invalid_version"
        assert (await two_versions.diff("1", "")).status_code == 422

    async def test_no_answer_text_is_in_the_reply(self, two_versions):
        assert "formResponse" not in (await two_versions.diff("1", "2")).text


class TestRestore:
    async def test_replaces_the_draft_and_changes_no_version(self, two_versions):
        form = two_versions
        before = (await form.versions()).json()
        stamp = before["draft"]["updatedAt"]
        response = await form.restore(1, stamp)
        assert response.status_code == 200, response.text
        assert response.json()["restoredVersion"] == 1
        draft = await form.draft()
        assert draft.title == "One"
        assert [f.id for f in draft.fields[0].properties.fields] == ["a", "b"]
        after = (await form.versions()).json()
        # history untouched: the same two versions, the same numbers
        assert [v["version"] for v in after["versions"]] == [2, 1]
        assert after["versions"][0]["current"] is True
        # the draft now differs from the live version, as work to publish
        assert after["draft"]["hasUnpublishedChanges"] is True
        # publishing it makes version 3, a copy of version 1's content
        await form.publish()
        three = (await form.diff("1", "3")).json()
        assert three["changed"] is False
        assert [v["version"] for v in (await form.versions()).json()["versions"]] == [
            3,
            2,
            1,
        ]

    async def test_unpublished_work_needs_confirmation(self, two_versions):
        form = two_versions
        stamp = await form.save([_q("a", "Full name"), _q("c", "Email"), _q("z", "WIP")], title="Two")
        refused = await form.restore(1, stamp)
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "draft_has_changes"
        assert (await form.draft()).title == "Two"
        confirmed = await form.restore(1, stamp, replace=True)
        assert confirmed.status_code == 200, confirmed.text
        assert [f.id for f in (await form.draft()).fields[0].properties.fields] == ["a", "b"]

    async def test_a_stale_draft_stamp_is_refused(self, two_versions):
        form = two_versions
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        # somebody else saves meanwhile
        await form.save([_q("a", "Full name"), _q("c", "Email")], title="Two edited")
        refused = await form.restore(1, stamp, replace=True)
        assert refused.status_code == 409
        assert refused.json()["code"] == "form_changed"
        assert (await form.draft()).title == "Two edited"

    async def test_an_unknown_version_is_404(self, two_versions):
        stamp = (await two_versions.versions()).json()["draft"]["updatedAt"]
        assert (await two_versions.restore(7, stamp)).status_code == 404

    async def test_restore_keeps_what_versions_do_not_carry(self, two_versions):
        # the share link and the workspace settings are not restored
        form = two_versions
        link = await container.workspace_form_repo().find_workspace_form(
            form.workspace.id, str(form.form.form_id)
        )
        stamp = (await form.versions()).json()["draft"]["updatedAt"]
        assert (await form.restore(1, stamp)).status_code == 200
        after = await container.workspace_form_repo().find_workspace_form(
            form.workspace.id, str(form.form.form_id)
        )
        assert after.settings.custom_url == link.settings.custom_url

    async def test_rules_in_an_old_version_are_not_restored_while_rules_are_off(
        self, two_versions, monkeypatch
    ):
        # a stored version with a rule, restored while FIELD_RULES_ENABLED is
        # off, goes through the same gate as a builder save
        form = two_versions
        monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
        rule = {
            "id": "r1",
            "when": {"conditions": [{"fieldId": "a", "comparison": "IS_EQUAL", "value": "x"}]},
            "then": {"required": True},
        }
        await form.save([_q("a", "Name"), _q("b", "Phone", properties={"rules": [rule]})], title="Rules")
        await form.publish()
        stamp = await form.save([_q("a")], title="Later")
        await form.publish()
        monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
        response = await form.restore(3, stamp)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "field_rules_disabled"
        assert (await form.draft()).title == "Later"


class TestPublishedBy:
    async def test_publishing_records_the_publisher_and_a_noop_publish_none(
        self, form
    ):
        await form.save([_q("a")], title="One")
        await form.publish()
        repo = container.form_repo()
        first = await repo.get_latest_version_of_form(form.form.form_id)
        assert first.published_by == str(testUser.id)
        # publishing an unchanged draft makes no new version
        await form.publish()
        assert (await repo.get_latest_version_of_form(form.form.form_id)).version == 1


class TestPublisherIsNeverServedAsAnId:
    async def test_no_form_read_carries_the_publisher_id(
        self, two_versions, client, test_user_cookies
    ):
        form = two_versions
        who = str(testUser.id)
        for url in (
            f"{form.base}/versions/2",
            f"{form.base}/versions/latest",
            f"{API}/workspaces/{form.workspace.id}/forms?published=true",
        ):
            response = await client.get(url, cookies=test_user_cookies)
            assert response.status_code == 200, (url, response.text)
            assert who not in response.text and "publishedBy" not in response.text, url
        # nor the respondent's or a public reader's copy
        public = await client.get(f"{form.base}/versions/latest")
        assert who not in public.text
