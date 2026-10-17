"""Chat proposals: the AI proposes (nothing is stored), the person accepts
or rejects. A FAKE provider only, never a model call."""

import asyncio
import datetime as dt
import json

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.test_form_ai_chat import _all_titles, _make_v2


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


def _base(workspace, form_id) -> str:
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/ai"


async def _stored(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


async def _propose(client, workspace, form_id, cookies, fake, ops, reply="Here you go."):
    fake.replies.append(json.dumps({"reply": reply, "ops": ops}))
    response = await client.post(
        _base(workspace, form_id) + "/chat",
        cookies=cookies,
        json={"message": "please change the form", "mode": "propose"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _accept(client, workspace, form_id, proposal_id, cookies, op_indexes=None):
    kwargs = {"cookies": cookies}
    if op_indexes is not None:
        kwargs["json"] = {"opIndexes": op_indexes}
    return client.post(
        _base(workspace, form_id) + f"/proposals/{proposal_id}/accept", **kwargs
    )


def _reject(client, workspace, form_id, proposal_id, cookies):
    return client.post(
        _base(workspace, form_id) + f"/proposals/{proposal_id}/reject",
        cookies=cookies,
    )


ADD_EMAIL = {
    "op": "add_field",
    "pageId": "page-1",
    "field": {"title": "Work email", "type": "email", "required": True},
}
RENAME = {"op": "update_form_info", "title": "Renamed by AI"}
# a new page, and a question on it named by the page's ref
NEW_PAGE = {"op": "add_page", "ref": "p2"}
ON_NEW_PAGE = {
    "op": "add_field",
    "pageId": "$ref:p2",
    "field": {"title": "Postcode", "type": "short_text"},
}


async def _session(proposal_id):
    return await container.form_ai_session_repo().get_or_404(
        PydanticObjectId(proposal_id.split("-")[0])
    )


def _record(session, proposal_id):
    for message in session.messages:
        if (message.get("proposal") or {}).get("id") == proposal_id:
            return message["proposal"]
    raise AssertionError("proposal not in the session")


class TestProposals:
    async def test_propose_stores_nothing_but_the_turn(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        before = (await _stored(form_id)).model_dump()

        body = await _propose(
            client, workspace, form_id, test_user_cookies, fake_provider, [ADD_EMAIL, RENAME]
        )

        assert body["form"] is None
        proposal = body["proposal"]
        assert proposal["summary"] == "Here you go."
        assert [r["ok"] for r in proposal["results"]] == [True, True]
        assert len(proposal["ops"]) == 2
        # the proposed form, the diff and what each op changes
        assert proposal["form"]["title"] == "Renamed by AI"
        assert "updatedAt" not in proposal["form"]
        added = proposal["diff"]["fields"]["added"]
        assert len(added) == 1 and added[0]["path"] == "/pages/0/fields/1"
        assert {"path": "/title", "before": before["title"], "after": "Renamed by AI"} in (
            proposal["diff"]["form"]
        )
        assert [s["index"] for s in proposal["steps"]] == [0, 1]
        assert proposal["steps"][0]["diff"]["fields"]["added"]
        assert not proposal["steps"][0]["diff"]["form"]
        assert proposal["steps"][1]["diff"]["form"][0]["path"] == "/title"

        # the form is untouched
        assert (await _stored(form_id)).model_dump() == before
        # the turn is in the history, marked as proposed
        session = await _session(proposal["id"])
        assert session.messages[1]["proposal"]["status"] == "proposed"
        assert session.messages[1]["ops"][0]["op"] == "add_field"

    async def test_a_turn_without_changes_has_no_proposal(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        body = await _propose(
            client, workspace, workspace_form.form_id, test_user_cookies, fake_provider, []
        )
        assert body["proposal"] is None and body["form"] is None

    async def test_apply_stays_the_default(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        fake_provider.replies.append(json.dumps({"reply": "Done.", "ops": [RENAME]}))
        response = await client.post(
            _base(workspace, workspace_form.form_id) + "/chat",
            cookies=test_user_cookies,
            json={"message": "rename it"},
        )
        assert response.status_code == 200
        assert response.json()["proposal"] is None
        assert (await _stored(workspace_form.form_id)).title == "Renamed by AI"

    async def test_accept_all(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        proposal = (
            await _propose(
                client, workspace, form_id, test_user_cookies, fake_provider, [ADD_EMAIL, RENAME]
            )
        )["proposal"]

        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "accepted"
        assert body["acceptedOpIndexes"] == [0, 1]
        assert [r["index"] for r in body["results"]] == [0, 1]
        assert body["form"]["title"] == "Renamed by AI"

        stored = await _stored(form_id)
        assert stored.title == "Renamed by AI"
        assert "Work email" in _all_titles(stored)
        # the reply carries the stored version for the editor's next save
        assert body["form"]["updatedAt"] == stored.updated_at.isoformat()
        assert _record(await _session(proposal["id"]), proposal["id"])["status"] == "accepted"

        # only once
        again = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert again.status_code == 409
        assert again.json()["code"] == "proposal_closed"
        assert _all_titles(await _stored(form_id)).count("Work email") == 1

    async def test_accept_a_subset(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        title_before = (await _stored(form_id)).title
        proposal = (
            await _propose(
                client, workspace, form_id, test_user_cookies, fake_provider, [ADD_EMAIL, RENAME]
            )
        )["proposal"]

        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [0]
        )
        assert response.status_code == 200, response.text
        assert response.json()["acceptedOpIndexes"] == [0]
        stored = await _stored(form_id)
        assert "Work email" in _all_titles(stored)
        assert stored.title == title_before

    async def test_a_subset_needs_the_ops_its_refs_name(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        before = (await _stored(form_id)).model_dump()
        proposal = (
            await _propose(
                client,
                workspace,
                form_id,
                test_user_cookies,
                fake_provider,
                [NEW_PAGE, ON_NEW_PAGE, RENAME],
            )
        )["proposal"]
        assert [s["requires"] for s in proposal["steps"]] == [[], [0], []]

        # the question without the page it goes on
        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [1, 2]
        )
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "proposal_dependency"
        assert body["errors"] == [
            {
                "index": 1,
                "requires": [0],
                "message": "Change #2 builds on change #1, which is not accepted. "
                "Accept it too, or leave #2 out.",
            }
        ]
        # nothing changed, and the proposal is still open
        assert (await _stored(form_id)).model_dump() == before

        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [0, 1]
        )
        assert response.status_code == 200, response.text
        stored = await _stored(form_id)
        assert "Postcode" in _all_titles(stored)
        assert stored.title == before["title"]

    async def test_an_op_that_failed_when_proposed_cannot_be_chosen(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        proposal = (
            await _propose(
                client,
                workspace,
                form_id,
                test_user_cookies,
                fake_provider,
                [{"op": "remove_field", "fieldId": "does-not-exist"}, RENAME],
            )
        )["proposal"]
        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [0, 1]
        )
        assert response.status_code == 422
        assert response.json()["code"] == "proposal_invalid_selection"
        assert response.json()["errors"][0]["index"] == 0
        # all that worked
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200
        assert response.json()["acceptedOpIndexes"] == [1]

    async def test_a_proposal_for_an_older_version_is_stale(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        """The reported case: a section title proposed for page 1 must not
        land on a page inserted in front of it since."""
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        proposal = (
            await _propose(
                client,
                workspace,
                form_id,
                test_user_cookies,
                fake_provider,
                [
                    {"op": "set_section_title", "pageIndex": 0, "title": "About you"},
                    RENAME,
                ],
            )
        )["proposal"]

        # meanwhile another save puts a page in front of page 1
        stored = await _stored(form_id)
        new_page = stored.fields[0].model_copy(deep=True, update={"id": "page-0"})
        new_page.properties.fields = []
        stored.fields = [new_page] + stored.fields
        await container.form_repo().save_form(stored)
        before = (await _stored(form_id)).model_dump()

        for op_indexes in (None, [0], [1]):
            response = await _accept(
                client, workspace, form_id, proposal["id"], test_user_cookies, op_indexes
            )
            assert response.status_code == 409, op_indexes
            body = response.json()
            assert body["code"] == "proposal_stale"
            assert body["message"] == "This form changed since the suggestion. Ask again."
        # nothing landed anywhere
        assert (await _stored(form_id)).model_dump() == before

    async def test_the_editor_saving_the_same_content_is_still_a_new_version(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        await container.form_repo().save_form(await _stored(form_id))
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 409
        assert response.json()["code"] == "proposal_stale"

    async def test_a_subset_must_do_what_was_shown(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        """Positions move with the ops before: without them a chosen op
        could change something else than its line said."""
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        stored = await _stored(form_id)
        second = stored.fields[0].model_copy(deep=True, update={"id": "page-2", "index": 1})
        second.properties.fields = []
        stored.fields = stored.fields + [second]
        await container.form_repo().save_form(stored)
        before = (await _stored(form_id)).model_dump()

        proposal = (
            await _propose(
                client,
                workspace,
                form_id,
                test_user_cookies,
                fake_provider,
                [
                    # a page in front: "page index 1" is then the first page
                    {"op": "add_page", "index": 0},
                    {"op": "set_section_title", "pageIndex": 1, "title": "About you"},
                    # "B" right after the new "A", before "Your name"
                    {
                        "op": "add_field",
                        "pageId": "page-1",
                        "index": 0,
                        "field": {"title": "A", "type": "short_text"},
                    },
                    {
                        "op": "add_field",
                        "pageId": "page-1",
                        "index": 1,
                        "field": {"title": "B", "type": "short_text"},
                    },
                    RENAME,
                ],
            )
        )["proposal"]
        assert all(r["ok"] for r in proposal["results"])

        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [1, 3, 4]
        )
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "proposal_selection_changes_meaning"
        assert [e["index"] for e in body["errors"]] == [1, 3]
        assert "change #2 would not do what was shown" in body["errors"][0]["message"]
        assert (await _stored(form_id)).model_dump() == before

        # what stands on its own can be accepted alone
        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [2, 4]
        )
        assert response.status_code == 200, response.text
        stored = await _stored(form_id)
        assert stored.title == "Renamed by AI"
        assert _all_titles(stored)[:2] == ["A", "Your name"]

    async def test_two_accepts_at_once_apply_it_once(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        proposal = (
            await _propose(
                client, workspace, form_id, test_user_cookies, fake_provider, [ADD_EMAIL]
            )
        )["proposal"]
        first, second = await asyncio.gather(
            _accept(client, workspace, form_id, proposal["id"], test_user_cookies),
            _accept(client, workspace, form_id, proposal["id"], test_user_cookies),
        )
        assert sorted([first.status_code, second.status_code]) == [200, 409]
        assert _all_titles(await _stored(form_id)).count("Work email") == 1

    async def test_the_size_limits_hold_when_proposing_and_accepting(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        from backend.app.services.ai import ops as ops_module

        form_id = workspace_form.form_id
        await _make_v2(await _stored(form_id))
        monkeypatch.setattr(ops_module, "MAX_PAGES", 2)
        proposal = (
            await _propose(
                client,
                workspace,
                form_id,
                test_user_cookies,
                fake_provider,
                [{"op": "add_page"}, {"op": "add_page"}, RENAME],
            )
        )["proposal"]
        assert [r["ok"] for r in proposal["results"]] == [True, False, False]
        assert "at most 2 pages" in proposal["results"][1]["message"]
        assert [s["index"] for s in proposal["steps"]] == [0]

        # the limit is lower now: accepting cannot pass it
        monkeypatch.setattr(ops_module, "MAX_PAGES", 1)
        before = (await _stored(form_id)).model_dump()
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 409
        assert response.json()["code"] == "proposal_stale"
        assert "at most 1 pages" in response.json()["errors"][0]["message"]
        assert (await _stored(form_id)).model_dump() == before

    async def test_accept_and_reject_at_once_have_one_winner(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        title_before = (await _stored(form_id)).title
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        accept, reject = await asyncio.gather(
            _accept(client, workspace, form_id, proposal["id"], test_user_cookies),
            _reject(client, workspace, form_id, proposal["id"], test_user_cookies),
        )
        assert sorted([accept.status_code, reject.status_code]) == [200, 409]
        status = _record(await _session(proposal["id"]), proposal["id"])["status"]
        title = (await _stored(form_id)).title
        if accept.status_code == 200:
            assert status == "accepted" and title == "Renamed by AI"
        else:
            assert status == "rejected" and title == title_before

    async def test_an_unexpected_error_leaves_it_open_for_a_retry(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        from backend.app.services.ai import chat as chat_module

        form_id = workspace_form.form_id
        before = (await _stored(form_id)).model_dump()
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]

        real_persist = chat_module.persist_form

        async def storage_down(*args, **kwargs):
            raise RuntimeError("storage unavailable")

        monkeypatch.setattr(chat_module, "persist_form", storage_down)
        try:
            response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
            assert response.status_code == 500
        except RuntimeError:
            pass  # the test transport passes the app's error through
        record = _record(await _session(proposal["id"]), proposal["id"])
        assert record["status"] == "proposed"
        assert record["attempt"] == 1
        assert (await _stored(form_id)).model_dump() == before

        # the retry decides it, once
        monkeypatch.setattr(chat_module, "persist_form", real_persist)
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200, response.text
        assert (await _stored(form_id)).title == "Renamed by AI"
        again = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert again.status_code == 409
        assert again.json()["code"] == "proposal_closed"

    async def test_a_form_deleted_during_accept_is_not_a_success(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        from backend.app.services.ai import chat as chat_module

        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        real_persist = chat_module.persist_form

        async def deleted_first(*args, **kwargs):
            await container.form_repo().delete_form(form_id)
            return await real_persist(*args, **kwargs)

        monkeypatch.setattr(chat_module, "persist_form", deleted_first)
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 404
        assert response.json() == {
            "code": "form_not_found",
            "message": "This form no longer exists. Nothing was changed.",
        }
        assert await _stored(form_id) is None
        assert _record(await _session(proposal["id"]), proposal["id"])["status"] == "failed"

    async def test_an_expired_proposal_is_gone(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        session = await _session(proposal["id"])
        past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=1)
        _record(session, proposal["id"])["expires_at"] = past.isoformat()
        await container.form_ai_session_repo().save(session)

        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 410
        assert response.json()["code"] == "proposal_expired"
        assert (await _stored(form_id)).title != "Renamed by AI"

    async def test_a_chat_turn_saved_meanwhile_keeps_the_decision(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        body = await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        proposal_id = body["proposal"]["id"]
        # a turn that read the session before the proposal was rejected
        stale_copy = await _session(proposal_id)
        assert (await _reject(client, workspace, form_id, proposal_id, test_user_cookies)).status_code == 200
        # ... and saves it afterwards, as chat_edit does
        service = container.form_ai_chat_service()
        await service._keep_proposal_statuses(stale_copy)
        await container.form_ai_session_repo().save(stale_copy)
        assert _record(await _session(proposal_id), proposal_id)["status"] == "rejected"

    async def test_reject(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        before = (await _stored(form_id)).model_dump()
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]

        response = await _reject(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200
        assert response.json() == {"proposalId": proposal["id"], "status": "rejected"}
        assert _record(await _session(proposal["id"]), proposal["id"])["status"] == "rejected"
        # again is fine; accepting is not
        again = await _reject(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert again.status_code == 200
        accept = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert accept.status_code == 409
        assert accept.json()["code"] == "proposal_closed"
        assert (await _stored(form_id)).model_dump() == before

    async def test_the_next_turn_knows_what_was_not_applied(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
        form_id = workspace_form.form_id
        body = await _propose(
            client, workspace, form_id, test_user_cookies, fake_provider, [RENAME], "Renamed."
        )
        fake_provider.replies.append(json.dumps({"reply": "Okay.", "ops": []}))
        await client.post(
            _base(workspace, form_id) + "/chat",
            cookies=test_user_cookies,
            json={"message": "and now?", "mode": "propose", "sessionId": body["sessionId"]},
        )
        history = fake_provider.calls[1]["messages"]
        assert history[1]["content"] == (
            "Renamed.\n(These changes were proposed but not applied.)"
        )

    async def test_outsiders_and_unknown_proposals(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        test_user_cookies_1,
        fake_provider,
    ):
        form_id = workspace_form.form_id
        before = (await _stored(form_id)).model_dump()
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]

        for call in (_accept, _reject):
            response = await call(
                client, workspace, form_id, proposal["id"], test_user_cookies_1
            )
            assert response.status_code == 403
        # an id of no proposal, or of another form, reads as none
        for proposal_id in (
            "nonsense",
            f"{PydanticObjectId()}-0123456789abcdef",
            proposal["id"][:-1] + ("0" if proposal["id"][-1] != "0" else "1"),
        ):
            response = await _accept(
                client, workspace, form_id, proposal_id, test_user_cookies
            )
            assert response.status_code == 404
        response = await _accept(
            client, workspace, str(PydanticObjectId()), proposal["id"], test_user_cookies
        )
        assert response.status_code == 404
        assert (await _stored(form_id)).model_dump() == before


def _fail_accepted_status(monkeypatch, times=None):
    """Make writing a proposal's ``accepted`` status fail (the first
    ``times`` writes, or every one); other writes go through. Returns the
    list of failed writes."""
    from backend.app.services.ai import proposals as proposals_module

    monkeypatch.setattr(proposals_module, "DECISION_WRITE_RETRY_DELAYS", (0, 0))
    repo = container.form_ai_proposal_service()._session_repo
    real = repo.update_proposal
    failed = []

    async def flaky(session_id, proposal_id, fields, only_if_status=None):
        if fields.get("status") == "accepted" and (times is None or len(failed) < times):
            failed.append(fields)
            raise RuntimeError("session storage unavailable")
        return await real(session_id, proposal_id, fields, only_if_status=only_if_status)

    monkeypatch.setattr(repo, "update_proposal", flaky)
    return failed


class TestAcceptedStatusWrite:
    """The form is written, then the ``accepted`` status: when that second
    write fails, the proposal must not read as "busy" until it expires."""

    async def test_the_status_write_is_retried(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        failed = _fail_accepted_status(monkeypatch, times=2)

        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200, response.text
        assert len(failed) == 2
        record = _record(await _session(proposal["id"]), proposal["id"])
        assert record["status"] == "accepted"
        assert record["accepted_op_indexes"] == [0]

    async def test_an_unwritten_status_still_reads_as_accepted(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        failed = _fail_accepted_status(monkeypatch)

        # the form is written: a success, though the status is not
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"
        assert len(failed) == 3  # the first try and two retries
        stored = await _stored(form_id)
        assert stored.title == "Renamed by AI"
        assert _record(await _session(proposal["id"]), proposal["id"])["status"] == "proposed"

        # neither "busy" nor "stale": accepted, and applied only once
        for call in (_accept, _reject):
            again = await call(client, workspace, form_id, proposal["id"], test_user_cookies)
            assert again.status_code == 409, again.text
            assert again.json()["code"] == "proposal_closed"
            assert "already accepted" in again.json()["message"]
        assert (await _stored(form_id)).model_dump() == stored.model_dump()

        # once the session can be written again, the status is recorded
        monkeypatch.undo()
        again = await _reject(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert again.status_code == 409
        assert again.json()["code"] == "proposal_closed"
        assert _record(await _session(proposal["id"]), proposal["id"])["status"] == "accepted"

    async def test_only_the_version_the_accept_wrote_reads_as_accepted(
        self,
        monkeypatch,
        client: AsyncClient,
        workspace,
        workspace_form,
        test_user_cookies,
        fake_provider,
    ):
        from backend.app.services.form_writes import persist_form

        form_id = workspace_form.form_id
        proposal = (
            await _propose(client, workspace, form_id, test_user_cookies, fake_provider, [RENAME])
        )["proposal"]
        _fail_accepted_status(monkeypatch)
        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 200, response.text

        # the editor saves again: the stored form is no longer that version
        stored = await _stored(form_id)
        edited = StandardForm(**stored.model_dump())
        edited.title = "Edited later"
        assert await persist_form(
            container.form_repo(), stored, edited, expected_updated_at=stored.updated_at
        )
        again = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert again.status_code == 409
        assert again.json()["code"] == "proposal_stale"
        assert (await _stored(form_id)).title == "Edited later"
