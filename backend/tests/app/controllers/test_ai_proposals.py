"""Chat proposals: the AI proposes (nothing is stored), the person accepts
or rejects. A FAKE provider only, never a model call."""

import asyncio
import datetime as dt
import json

import pytest
from beanie import PydanticObjectId
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

    async def test_a_stale_proposal_is_refused_with_the_op_errors(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies, fake_provider
    ):
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
                    RENAME,
                    {"op": "update_field", "fieldId": "field-1", "patch": {"title": "Full name"}},
                ],
            )
        )["proposal"]

        # meanwhile, the question it changes is removed in the editor
        stored = await _stored(form_id)
        stored.fields[0].properties.fields = []
        await container.form_repo().save_form(stored)
        before = (await _stored(form_id)).model_dump()

        response = await _accept(client, workspace, form_id, proposal["id"], test_user_cookies)
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "proposal_stale"
        assert [e["index"] for e in body["errors"]] == [1]
        assert "field-1" in body["errors"][0]["message"]
        # all or nothing: the rename was not applied either
        assert (await _stored(form_id)).model_dump() == before

        # a change that still applies can be accepted on its own
        response = await _accept(
            client, workspace, form_id, proposal["id"], test_user_cookies, [0]
        )
        assert response.status_code == 200, response.text
        assert (await _stored(form_id)).title == "Renamed by AI"

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
