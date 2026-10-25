"""The builder's optimistic concurrency on whole-form saves: a save based on
an older draft is refused (409) instead of overwriting newer changes."""

import asyncio
import datetime as dt
import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.repositories.postgres.forms import PostgresFormRepository
from backend.app.services.ai.chat import camel_form_reply
from backend.app.services.form_concurrency import (
    FORM_CHANGED_CODE,
    _in_ms,
    ensure_not_changed_since,
    is_changed_since,
    next_updated_at,
    parse_expected_updated_at,
)
from common.models.standard_form import StandardForm


@pytest.fixture()
def form_url(workspace, workspace_form):
    return f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}"


async def _patch(client, url, cookies, body, expected=None):
    data = {"form_body": json.dumps(body)}
    if expected is not None:
        data["expected_updated_at"] = expected
    return await client.patch(url, cookies=cookies, data=data)


class TestFormSaveConflict:
    async def test_a_save_returns_the_new_updated_at(
        self, client: AsyncClient, form_url, workspace_form, test_user_cookies
    ):
        before = workspace_form.updated_at
        response = await _patch(client, form_url, test_user_cookies, {"title": "One"})
        assert response.status_code == 200
        updated_at = response.json().get("updatedAt")
        assert updated_at
        assert is_changed_since(parse_expected_updated_at(updated_at), before)

    async def test_saving_on_top_of_the_latest_version_works(
        self, client: AsyncClient, form_url, test_user_cookies
    ):
        first = await _patch(client, form_url, test_user_cookies, {"title": "One"})
        seen = first.json()["updatedAt"]
        second = await _patch(
            client, form_url, test_user_cookies, {"title": "Two"}, expected=seen
        )
        assert second.status_code == 200
        assert second.json()["title"] == "Two"
        # and again from what that save returned
        third = await _patch(
            client,
            form_url,
            test_user_cookies,
            {"title": "Three"},
            expected=second.json()["updatedAt"],
        )
        assert third.status_code == 200

    async def test_a_save_from_an_older_copy_is_refused_and_writes_nothing(
        self, client: AsyncClient, form_url, workspace_form, test_user_cookies
    ):
        tab_a = await _patch(client, form_url, test_user_cookies, {"title": "A"})
        seen_by_both = tab_a.json()["updatedAt"]
        tab_b = await _patch(
            client,
            form_url,
            test_user_cookies,
            {"title": "From B"},
            expected=seen_by_both,
        )
        assert tab_b.status_code == 200

        stale = await _patch(
            client,
            form_url,
            test_user_cookies,
            {"title": "Stale A", "settings": {"privacyPolicyUrl": "https://a.example"}},
            expected=seen_by_both,
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == FORM_CHANGED_CODE

        stored = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert stored.title == "From B"
        # the refused save's settings were not written either
        latest = await _patch(client, form_url, test_user_cookies, {"title": "C"})
        assert (latest.json().get("settings") or {}).get(
            "privacyPolicyUrl"
        ) != "https://a.example"

    async def test_callers_that_send_no_version_keep_saving(
        self, client: AsyncClient, form_url, test_user_cookies
    ):
        await _patch(client, form_url, test_user_cookies, {"title": "One"})
        response = await _patch(client, form_url, test_user_cookies, {"title": "Two"})
        assert response.status_code == 200
        assert response.json()["title"] == "Two"

    async def test_the_loaded_form_carries_updated_at(
        self,
        client: AsyncClient,
        form_url,
        test_user_cookies,
        mock_aiohttp_get_request,
    ):
        with mock_aiohttp_get_request:
            loaded = await client.get(form_url, cookies=test_user_cookies)
        seen = loaded.json().get("updatedAt")
        assert seen
        response = await _patch(
            client, form_url, test_user_cookies, {"title": "One"}, expected=seen
        )
        assert response.status_code == 200

    async def test_an_unreadable_version_is_a_client_error(
        self, client: AsyncClient, form_url, test_user_cookies
    ):
        response = await _patch(
            client, form_url, test_user_cookies, {"title": "One"}, expected="yesterday"
        )
        assert response.status_code == 422

    async def test_a_form_without_pages_can_be_saved(
        self, client: AsyncClient, form_url, workspace_form, test_user_cookies
    ):
        response = await _patch(
            client, form_url, test_user_cookies, {"title": "Empty", "fields": []}
        )
        assert response.status_code == 200
        stored = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert stored.fields == []


@pytest.fixture()
def saves_read_together(monkeypatch):
    """Two conditional saves both read the stored draft before either
    writes: each waits after its read until the other has read too. That
    gets both past every check made on what they read, so only the
    conditional write can tell them apart."""
    barrier = asyncio.Barrier(2)
    reads = []
    read = PostgresFormRepository._stored_draft

    async def gated(self, form_id):
        found = await read(self, form_id)
        reads.append(form_id)
        if len(reads) <= 2:  # the two racing saves; later ones run freely
            await asyncio.wait_for(barrier.wait(), timeout=10)
        return found

    monkeypatch.setattr(PostgresFormRepository, "_stored_draft", gated)


def _one_winner(results):
    saved = [r for r in results if not isinstance(r, BaseException)]
    refused = [r for r in results if isinstance(r, BaseException)]
    assert len(saved) == 1 and len(refused) == 1, results
    assert isinstance(refused[0], HTTPException)
    assert refused[0].status_code == 409
    return saved[0]


class TestSimultaneousSaves:
    """Two saves based on the same version landing at the same moment."""

    async def test_the_repository_writes_only_one(
        self, workspace_form, saves_read_together
    ):
        repository = container.form_repo()
        stored = await repository.get_form_document_by_id(workspace_form.form_id)
        expected = stored.updated_at

        results = await asyncio.gather(
            repository.update_form_if_unchanged(
                form_id=workspace_form.form_id,
                form=StandardForm(title="Save A"),
                expected_updated_at=expected,
            ),
            repository.update_form_if_unchanged(
                form_id=workspace_form.form_id,
                form=StandardForm(title="Save B"),
                expected_updated_at=expected,
            ),
            return_exceptions=True,
        )
        winner = _one_winner(results)

        after = await repository.get_form_document_by_id(workspace_form.form_id)
        assert after.title == winner.title
        # the write set updated_at itself: what it returned is what is stored
        assert after.updated_at == winner.updated_at
        assert is_changed_since(after.updated_at, expected)

    async def test_the_endpoint_answers_409_and_writes_nothing_for_the_other(
        self,
        client: AsyncClient,
        form_url,
        workspace,
        workspace_form,
        test_user_cookies,
        saves_read_together,
    ):
        first = await _patch(client, form_url, test_user_cookies, {"title": "One"})
        seen = first.json()["updatedAt"]

        def save(name):
            return _patch(
                client,
                form_url,
                test_user_cookies,
                {
                    "title": f"From {name}",
                    "settings": {"privacyPolicyUrl": f"https://{name}.example"},
                },
                expected=seen,
            )

        responses = await asyncio.gather(save("a"), save("b"))
        codes = sorted(r.status_code for r in responses)
        assert codes == [200, 409], codes
        won = next(r for r in responses if r.status_code == 200).json()
        lost = next(r for r in responses if r.status_code == 409).json()
        assert lost["code"] == FORM_CHANGED_CODE

        stored = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert stored.title == won["title"]
        assert _in_ms(stored.updated_at) == _in_ms(
            parse_expected_updated_at(won["updatedAt"])
        )
        # the refused save's settings were not written either
        workspace_form_doc = await container.workspace_form_repo().find_workspace_form(
            workspace.id, workspace_form.form_id
        )
        winner = "a" if won["title"] == "From a" else "b"
        assert workspace_form_doc.settings.privacy_policy_url == (
            f"https://{winner}.example"
        )

        # and the winner's version is the one the next save builds on
        again = await _patch(
            client,
            form_url,
            test_user_cookies,
            {"title": "Next"},
            expected=won["updatedAt"],
        )
        assert again.status_code == 200


class TestVersionComparison:
    def test_milliseconds_decide(self):
        saved = dt.datetime(2026, 10, 17, 9, 0, 0, 123456, tzinfo=dt.timezone.utc)
        # stored values keep milliseconds: one reads back truncated
        stored = dt.datetime(2026, 10, 17, 9, 0, 0, 123000)
        assert not is_changed_since(stored, saved)
        assert is_changed_since(stored + dt.timedelta(milliseconds=1), saved)

    def test_naive_values_are_utc(self):
        aware = dt.datetime(2026, 10, 17, 9, 0, tzinfo=dt.timezone.utc)
        assert not is_changed_since(aware.replace(tzinfo=None), aware)
        later_elsewhere = dt.datetime(
            2026, 10, 17, 11, 0, 1, tzinfo=dt.timezone(dt.timedelta(hours=2))
        )
        assert is_changed_since(later_elsewhere, aware)

    def test_nothing_to_compare_never_conflicts(self):
        now = dt.datetime.now(dt.timezone.utc)
        assert not is_changed_since(None, now)
        assert not is_changed_since(now, None)
        assert parse_expected_updated_at(None) is None
        assert parse_expected_updated_at("") is None

    def test_iso_strings_with_z_parse(self):
        parsed = parse_expected_updated_at("2026-10-17T09:00:00.123Z")
        assert parsed == dt.datetime(
            2026, 10, 17, 9, 0, 0, 123000, tzinfo=dt.timezone.utc
        )

    def test_each_save_stores_a_newer_version(self):
        previous = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5)
        stamp = next_updated_at(previous)
        # in whole milliseconds, and later than the one before even when the
        # clock says otherwise (two saves in the same millisecond)
        assert stamp.microsecond % 1000 == 0
        assert is_changed_since(stamp, previous)
        assert _in_ms(stamp) == _in_ms(previous) + 1
        assert next_updated_at(None).tzinfo is not None

    def test_a_newer_draft_raises_409(self):
        now = dt.datetime.now(dt.timezone.utc)
        with pytest.raises(HTTPException) as raised:
            ensure_not_changed_since(now, now - dt.timedelta(seconds=5))
        assert raised.value.status_code == 409


def test_ai_replies_carry_the_stored_version():
    stamp = dt.datetime(2026, 10, 17, 9, 0, tzinfo=dt.timezone.utc)
    reply = camel_form_reply(
        StandardForm(form_id="f", title="T"), SimpleNamespace(updated_at=stamp)
    )
    assert reply["updatedAt"] == stamp.isoformat()
    assert reply["title"] == "T"
