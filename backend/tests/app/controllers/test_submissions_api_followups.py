"""Follow-ups of the submissions API: what the stored consent says, updates on a
response with a deletion request, a cancelled request after the write, and the
per-form burst budget."""

import asyncio
from types import SimpleNamespace

import pytest
from common.models.consent import Consent, ConsentCategory, ConsentType
from common.models.standard_form import StandardForm
from httpx import AsyncClient
from starlette.requests import Request

from backend.app.container import container
from backend.app.public_api import auth as public_auth
from backend.app.public_api.routes import _idempotent
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import text
from tests.app.controllers.test_submissions_api import (
    BASE,
    _answers_of,
    _auth,
    _body,
    _form,
    _key,
    _only_response,
    _submit,
)


@pytest.fixture(autouse=True)
def _switch_on(monkeypatch):
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)


def _item(consent_id, required, kind=ConsentType.CHECKBOX):
    return Consent(
        consent_id=consent_id,
        title=f"Item {consent_id}",
        description=f"The text of {consent_id}",
        required=required,
        type=kind,
        category=ConsentCategory.PURPOSE_OF_THE_FORM,
    )


async def _consent_form(workspace, items) -> str:
    """A published form with its own consent items (made by the service)."""
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Consent test",
            consent=items,
            fields=[
                {
                    "id": "s1",
                    "type": "slide",
                    "index": 0,
                    "properties": {
                        "fields": [
                            {
                                "id": "name",
                                "type": "short_text",
                                "title": "Name",
                                "validations": {"required": True},
                            }
                        ]
                    },
                }
            ],
        ),
        testUser,
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form.form_id


async def _stored_consent(response_id):
    [doc] = await container.form_response_repo().list_by_response_id(response_id)
    return {c.consent_id: c.accepted for c in doc.consent}, doc


CUSTOM = [
    _item("terms", True),
    _item("newsletter", False),
    _item("research", False),
    _item("rights", False, ConsentType.INFO),
]


class TestStoredConsent:
    async def test_the_form_s_own_items_are_what_is_judged_and_stored(
        self, client: AsyncClient, workspace
    ):
        form_id = await _consent_form(workspace, CUSTOM)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": "Ada"}))
        assert created.status_code == 201, created.text
        accepted, doc = await _stored_consent(created.json()["responseId"])
        # the required checkbox only; optional ones are not accepted; info has nothing to accept
        assert accepted == {
            "terms": True,
            "newsletter": False,
            "research": False,
            "rights": None,
        }
        assert doc.submission_source.consent_asserted is True
        # (the items are the form's own, not the defaults)
        assert {c.title for c in doc.consent} == {f"Item {i.consent_id}" for i in CUSTOM}

    async def test_an_optional_item_is_accepted_only_when_named(
        self, client: AsyncClient, workspace
    ):
        form_id = await _consent_form(workspace, CUSTOM)
        token = await _key(workspace)
        created = await _submit(
            client,
            token,
            form_id,
            _body({"name": "Ada"}, consentItems=["newsletter"]),
        )
        assert created.status_code == 201, created.text
        accepted, _ = await _stored_consent(created.json()["responseId"])
        assert accepted["terms"] is True
        assert accepted["newsletter"] is True
        assert accepted["research"] is False

    async def test_an_unknown_item_is_refused_and_nothing_is_stored(
        self, client: AsyncClient, workspace
    ):
        form_id = await _consent_form(workspace, CUSTOM)
        token = await _key(workspace)
        refused = await _submit(
            client, token, form_id, _body({"name": "Ada"}, consentItems=["nope"])
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "unknown_consent_item"
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_naming_items_does_not_replace_the_required_assertion(
        self, client: AsyncClient, workspace
    ):
        form_id = await _consent_form(workspace, CUSTOM)
        token = await _key(workspace)
        refused = await _submit(
            client,
            token,
            form_id,
            _body({"name": "Ada"}, consent=None, consentItems=["newsletter"]),
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "consent_required"
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_a_form_with_only_optional_items_needs_no_assertion(
        self, client: AsyncClient, workspace
    ):
        form_id = await _consent_form(
            workspace, [_item("newsletter", False), _item("research", False)]
        )
        token = await _key(workspace)
        created = await _submit(
            client,
            token,
            form_id,
            _body({"name": "Ada"}, consent=None, consentItems=["research"]),
        )
        assert created.status_code == 201, created.text
        accepted, doc = await _stored_consent(created.json()["responseId"])
        assert accepted == {"newsletter": False, "research": True}
        # nothing was asserted for a required item: there is none
        assert doc.submission_source.consent_asserted is False

    async def test_the_default_items_are_still_accepted_by_consent_true(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        accepted, _ = await _stored_consent(created.json()["responseId"])
        assert accepted == {"default_form_purpose": True, "responder_rights": None}

    @pytest.mark.parametrize("named", ["research", [1], ["x"] * 51])
    async def test_consent_items_must_be_a_list_of_ids(
        self, client: AsyncClient, workspace, named
    ):
        form_id = await _consent_form(workspace, CUSTOM)
        token = await _key(workspace)
        refused = await _submit(
            client, token, form_id, _body({"name": "Ada"}, consentItems=named)
        )
        assert refused.status_code == 422
        assert (await _only_response(workspace, form_id))[1] == 0


class TestDeletionRequests:
    async def test_a_response_with_an_open_deletion_request_takes_no_update(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        response_id = created.json()["responseId"]
        await container.form_response_service().request_for_response_deletion(
            workspace.id, response_id, testUser
        )
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "Rewritten"}},
            headers=_auth(token),
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "deletion_requested"
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_other_responses_of_the_form_are_still_updated(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        first = (await _submit(client, token, form_id, _body({"name": text("Ada")}))).json()
        second = (await _submit(client, token, form_id, _body({"name": text("Bo")}))).json()
        await container.form_response_service().request_for_response_deletion(
            workspace.id, first["responseId"], testUser
        )
        ok = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{second['responseId']}",
            json={"answers": {"name": "Bo B."}},
            headers=_auth(token),
        )
        assert ok.status_code == 200, ok.text


class TestCancelledAfterTheWrite:
    async def test_a_cancelled_request_still_finishes_the_idempotency_key(
        self, workspace
    ):
        """The client goes away while the write is running: the write commits
        and the key is finished with its answer, never released."""
        service = container.idempotency_service()
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/forms/f/submissions",
                "headers": [],
                "query_string": b"",
            }
        )
        caller = SimpleNamespace(key_id="cancel-key")
        committed = asyncio.Event()
        release = asyncio.Event()

        from fastapi.responses import JSONResponse

        async def run():
            await release.wait()
            committed.set()  # (the write is stored here)
            return JSONResponse({"responseId": "r1"}, status_code=201)

        task = asyncio.ensure_future(
            _idempotent(request, caller, "once", b"{}", "body", run)
        )
        await asyncio.sleep(0.05)
        task.cancel()  # the request is cancelled (the client disconnected)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not committed.is_set()
        release.set()
        for _ in range(100):
            await asyncio.sleep(0.02)
            if committed.is_set():
                break
        await asyncio.sleep(0.2)
        # the retry gets the stored 201, and the key is not free to write again
        replay = await service.begin(
            "cancel-key",
            "once",
            __import__(
                "backend.app.services.idempotency", fromlist=["request_hash"]
            ).request_hash("POST", "/forms/f/submissions", b"{}"),
        )
        assert replay is not None and replay.status_code == 201
        assert '"r1"' in replay.body

    async def test_a_failure_in_the_run_is_still_released_or_kept_as_before(
        self, client: AsyncClient, workspace
    ):
        # (the shield changes nothing for a request that is not cancelled)
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "plain-1"}
        bad = await _submit(client, token, form_id, _body({}), **headers)
        again = await _submit(client, token, form_id, _body({}), **headers)
        assert bad.status_code == again.status_code == 422
        assert again.headers["Idempotent-Replayed"] == "true"


class TestPerFormBudget:
    async def test_one_form_takes_a_fixed_number_of_writes_a_window(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(public_auth, "SUBMISSIONS_PER_FORM_PER_WINDOW", 3)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_WINDOW_SECONDS", 3600)
        busy = await _form(client, workspace)
        other = await _form(client, workspace)
        one, two = await _key(workspace), await _key(workspace)
        made = []
        for key in (one, two, one):
            sent = await _submit(client, key, busy, _body({"name": text("A")}))
            assert sent.status_code == 201, sent.text
            made.append(sent.json()["responseId"])
        # the form is out of budget for every key, creates and updates alike
        limited = await _submit(client, two, busy, _body({"name": text("B")}))
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"
        assert "this form" in limited.json()["message"]
        assert int(limited.headers["Retry-After"]) > 0
        updated = await client.patch(
            f"{BASE}/forms/{busy}/submissions/{made[0]}",
            json={"answers": {"name": "C"}},
            headers=_auth(one),
        )
        assert updated.status_code == 429
        assert (await _only_response(workspace, busy))[1] == 3
        # another form of the workspace has its own budget
        assert (
            await _submit(client, one, other, _body({"name": text("A")}))
        ).status_code == 201

    async def test_it_follows_the_off_switch_of_the_api_limits(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(public_auth, "SUBMISSIONS_PER_FORM_PER_WINDOW", 1)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_REQUESTS_PER_WINDOW", 0)
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        for _ in range(3):
            assert (
                await _submit(client, token, form_id, _body({"name": text("A")}))
            ).status_code == 201
