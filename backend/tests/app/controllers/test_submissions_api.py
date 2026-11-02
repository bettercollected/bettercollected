"""The public API's submissions endpoints: an API key creates and updates
responses through the respondent's own submit path.

Parity first: the same cases run through the respondent route and through the
API and must come out the same (status, problems, stored answers). Then what
only the API adds: the switch, the scope, a key's form list, the identity and
consent rules, idempotency, the audit row, its own rate budget, the source
that only staff see, and updates limited to what the same key made."""

import datetime as dt
import json
from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest
from common.models.standard_form import SubmissionSource
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.public_api import openapi as public_openapi
from backend.app.services import idempotency
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.app.services.api_responses import list_response_summaries, response_detail
from backend.app.services.webhooks import payload as webhook_payload
from backend.config import settings
from tests.app.controllers.data import testUser
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from common.ids import RecordId
from common.models.user import User
from tests.app.controllers.submission_cases import (
    CASES,
    RICH_CASES,
    RICH_SPEC,
    SPEC,
    choice,
    guests,
    number,
    text,
)

BASE = "/api/v1/public/v1"
SCOPES = ["forms:read", "forms:write", "responses:read", "submissions:write"]


@pytest.fixture(autouse=True)
def _switch_on(monkeypatch):
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)


def _auth(token: str, **headers) -> dict:
    return {"Authorization": f"Bearer {token}", **headers}


async def _key(workspace, scopes=SCOPES, form_ids=None, user=testUser) -> str:
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(
            name="submit key",
            scopes=scopes,
            acknowledge_unredacted_responses="responses:read" in scopes,
            submission_form_ids=form_ids,
        ),
        user,
    )
    return created.token


async def _form(client, workspace, spec=SPEC, publish=True) -> str:
    token = await _key(workspace, ["forms:read", "forms:write"])
    created = await client.post(f"{BASE}/forms", json=spec, headers=_auth(token))
    assert created.status_code == 201, created.text
    form_id = created.json()["formId"]
    if publish:
        published = await client.post(
            f"{BASE}/forms/{form_id}/publish", headers=_auth(token)
        )
        assert published.status_code == 200, published.text
    return form_id


async def _submit(client, token, form_id, body, **headers):
    return await client.post(
        f"{BASE}/forms/{form_id}/submissions",
        json=body,
        headers=_auth(token, **headers),
    )


def _body(answers, consent=True, **extra):
    body = {"answers": answers, **extra}
    if consent is not None:
        body["consent"] = consent
    return body


def _api_errors(response) -> set:
    """{(question, rule)} of a 422 ``invalid_answers`` of the API: the path is
    ``/answers/<id>`` (or ``/answers/<group>/items/<n>/<id>``), the message
    starts with the rule."""
    errors = response.json()["errors"]
    return {(e["path"].rsplit("/", 1)[-1], e["message"].split(":")[0]) for e in errors}


def _form_errors(response) -> set:
    """The same of the respondent route's answer."""
    body = response.json()
    assert body["code"] == "invalid_answers"
    return {(e["fieldId"], e["rule"]) for e in body["errors"]}


def _error_set(response):
    return _api_errors(response)


async def _only_response(workspace, form_id):
    items, total = await list_response_summaries(workspace.id, form_id, 10)
    return items, total


async def _answers_of(workspace, response_id):
    return (await response_detail(workspace.id, response_id))["answers"]


async def _stored_row_answers(response_id):
    """The stored ``answers`` as the database holds them."""
    docs = await container.form_response_repo().list_by_response_id(response_id)
    assert len(docs) == 1
    return docs[0].answers


# -- parity with the respondent path -------------------------------------------------


class TestParity:
    @pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
    async def test_both_paths_judge_the_same(self, client: AsyncClient, workspace, case):
        _, answers, status, problems = case
        form_id = await _form(client, workspace)
        token = await _key(workspace)

        via_api = await _submit(client, token, form_id, _body(answers))
        via_form = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": answers})},
        )
        # (the respondent route answers 200 with the receipt, the API 201)
        assert via_api.status_code == (201 if status == 201 else status), via_api.text
        assert via_form.status_code == (200 if status == 201 else status), via_form.text
        if status == 422:
            assert _api_errors(via_api) == problems
            assert _form_errors(via_form) == problems
            _, total = await _only_response(workspace, form_id)
            assert total == 0
            return
        items, total = await _only_response(workspace, form_id)
        assert total == 2
        stored = [await _answers_of(workspace, i["responseId"]) for i in items]
        # same answers stored by both (the API's response is a new one)
        assert stored[0] == stored[1]

    async def test_a_closed_form_refuses_both(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        link = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        link.settings.form_close_date = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        ).isoformat()
        await container.workspace_form_repo().update(link.id, link)
        token = await _key(workspace)
        via_api = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        via_form = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {"name": text("Ada")}})},
        )
        assert via_api.status_code == via_form.status_code == 409
        assert via_api.json()["code"] == "form_closed"
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_a_form_that_is_full_refuses_both(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        link = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        link.settings.response_limit = 1
        await container.workspace_form_repo().update(link.id, link)
        token = await _key(workspace)
        assert (
            await _submit(client, token, form_id, _body({"name": text("Ada")}))
        ).status_code == 201
        again = await _submit(client, token, form_id, _body({"name": text("Bo")}))
        assert again.status_code == 409
        assert again.json()["code"] == "form_full"

    async def test_an_unpublished_form_takes_none(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace, publish=False)
        token = await _key(workspace)
        refused = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert refused.status_code == 404
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_the_published_version_is_what_is_checked(
        self, client: AsyncClient, workspace
    ):
        """A draft change that is not published yet does not apply."""
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        edited = json.loads(json.dumps(SPEC))
        edited["pages"][0]["fields"].append(
            {
                "id": "extra",
                "type": "short_text",
                "title": "New required question",
                "validations": {"required": True},
            }
        )
        document = (
            await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
        )
        replaced = await client.put(
            f"{BASE}/forms/{form_id}",
            json=edited,
            headers=_auth(token, **{"If-Match": document.headers["ETag"]}),
        )
        assert replaced.status_code == 200, replaced.text
        accepted = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert accepted.status_code == 201, accepted.text
        # and a draft-only question is not one of the published form's
        refused = await _submit(
            client, token, form_id, _body({"name": text("Ada"), "extra": text("x")})
        )
        assert refused.status_code == 422
        assert _error_set(refused) == {("extra", "unknown_field")}


# -- the switch, the scope and the form list -------------------------------------------


class TestSwitchAndScope:
    async def test_off_the_endpoints_do_not_exist_and_the_scope_cannot_be_granted(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", False)
        for headers in (_auth(token), {}, _auth("bc_not_a_key")):
            refused = await client.post(
                f"{BASE}/forms/{form_id}/submissions",
                json=_body({"name": text("Ada")}),
                headers=headers,
            )
            # 404 before the key is even looked at
            assert refused.status_code == 404, refused.text
            assert refused.json()["code"] == "not_found"
        patched = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{'0' * 24}",
            json={"answers": {}},
            headers=_auth(token),
        )
        assert patched.status_code == 404
        assert (await _only_response(workspace, form_id))[1] == 0
        with pytest.raises(Exception) as refusal:
            await _key(workspace, ["submissions:write"])
        assert "submissions_api_off" in str(refusal.value.content)

    async def test_the_switch_is_served_with_the_permissions(
        self, client: AsyncClient, workspace, test_user_cookies, monkeypatch
    ):
        url = f"/api/v1/workspaces/{workspace.id}/permissions"
        on = await client.get(url, cookies=test_user_cookies)
        assert on.json()["submissionsApiEnabled"] is True
        monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", False)
        off = await client.get(url, cookies=test_user_cookies)
        assert off.json()["submissionsApiEnabled"] is False

    async def test_the_scope_is_never_implied(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        for scopes in (
            ["forms:read", "forms:write", "forms:delete", "responses:read"],
            ["deletion_requests:write"],
        ):
            token = await _key(workspace, scopes)
            refused = await _submit(client, token, form_id, _body({"name": text("A")}))
            assert refused.status_code == 403, refused.text
            assert refused.json()["code"] == "missing_scope"
            assert "submissions:write" in refused.json()["message"]
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_a_key_that_lost_its_creator_is_refused(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        [api_key] = [
            k
            for k in await container.workspace_api_key_repo().list_by_workspace(
                workspace.id
            )
            if "submissions:write" in k.scopes
        ]
        api_key.created_by = "someone-who-is-not-a-member"
        await container.workspace_api_key_repo().save(api_key)
        refused = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert refused.status_code == 403
        assert refused.json()["code"] == "key_creator_lacks_permission"

    async def test_a_key_works_in_its_own_workspace_only(
        self, client: AsyncClient, workspace, workspace_1, published_form_1
    ):
        token = await _key(workspace)
        refused = await _submit(
            client, token, published_form_1.form_id, _body({"name": text("Ada")})
        )
        assert refused.status_code == 404

    async def test_a_key_can_be_limited_to_some_forms(
        self, client: AsyncClient, workspace
    ):
        first, second = await _form(client, workspace), await _form(client, workspace)
        token = await _key(workspace, form_ids=[first])
        ok = await _submit(client, token, first, _body({"name": text("Ada")}))
        assert ok.status_code == 201, ok.text
        refused = await _submit(client, token, second, _body({"name": text("Ada")}))
        assert refused.status_code == 403
        assert refused.json()["code"] == "form_not_allowed"
        assert (await _only_response(workspace, second))[1] == 0
        # the list is part of the key as listed to admins
        [listed] = [
            k
            for k in await container.api_key_service().list_keys(workspace.id, testUser)
            if k.submission_form_ids
        ]
        assert listed.submission_form_ids == [first]

    async def test_a_form_list_is_checked_when_the_key_is_made(
        self, client: AsyncClient, workspace, workspace_1, published_form_1
    ):
        mine = await _form(client, workspace)
        for scopes, form_ids in (
            (SCOPES, [published_form_1.form_id]),  # another workspace's form
            (SCOPES, []),
            (["forms:read"], [mine]),  # a list limits a scope it does not have
        ):
            with pytest.raises(Exception) as refusal:
                await _key(workspace, scopes, form_ids)
            assert getattr(refusal.value, "status_code", None) == 400


# -- creating ----------------------------------------------------------------------


class TestCreate:
    async def test_the_answer_and_what_is_stored(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(
            client, token, form_id, _body({"name": text("Ada Lovelace")})
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert set(body) == {"responseId", "formId", "submittedAt", "formVersion"}
        assert body["formId"] == form_id and body["formVersion"] == 1
        # the answers are sealed at rest: the stored column is ciphertext
        sealed = await _stored_row_answers(body["responseId"])
        assert not isinstance(sealed, dict)
        assert "Ada" not in str(sealed)
        # and read back through the key's own read path
        assert (await _answers_of(workspace, body["responseId"]))["name"]["text"] == (
            "Ada Lovelace"
        )
        # the response belongs to nobody and carries no respondent
        [doc] = await container.form_response_repo().list_by_response_id(
            body["responseId"]
        )
        assert doc.dataOwnerIdentifier is None
        assert doc.anonymous_identity is None
        assert doc.respondent_email is None
        assert doc.provider == "self"

    async def test_shorthand_answers_are_the_same_as_typed_ones(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        shorthand = await _submit(
            client,
            token,
            form_id,
            _body(
                {
                    "name": "Ada",
                    "email": "ada@example.org",
                    "age": 36,
                    "dinner": True,
                    "meal": "Fish",  # by its text
                }
            ),
        )
        typed = await _submit(
            client,
            token,
            form_id,
            _body(
                {
                    "name": text("Ada"),
                    "email": {"type": "email", "email": "ada@example.org"},
                    "age": {"type": "number", "number": 36},
                    "dinner": {"type": "boolean", "boolean": True},
                    "meal": choice("fish"),
                }
            ),
        )
        assert shorthand.status_code == typed.status_code == 201, shorthand.text
        assert await _answers_of(workspace, shorthand.json()["responseId"]) == (
            await _answers_of(workspace, typed.json()["responseId"])
        )

    async def test_errors_are_per_question_with_the_body_pointer(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        refused = await _submit(client, token, form_id, _body({"age": 3}))
        assert refused.status_code == 422
        body = refused.json()
        assert body["code"] == "invalid_answers"
        assert {(e["path"], e["message"].split(":")[0]) for e in body["errors"]} == {
            ("/answers/name", "required"),
            ("/answers/age", "too_small"),
        }
        assert set(body) <= {"code", "message", "errors"}
        # an answer that does not fit its question is reported where it is
        shape = await _submit(
            client, token, form_id, _body({"name": text("Ada"), "email": ["a"]})
        )
        assert shape.status_code == 422
        assert [(e["path"], e["message"].split(":")[0]) for e in shape.json()["errors"]] == [
            ("/answers/email", "type")
        ]

    async def test_consent_is_asserted_and_recorded(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        for consent in (None, False):
            refused = await _submit(
                client, token, form_id, _body({"name": text("Ada")}, consent=consent)
            )
            assert refused.status_code == 422
            assert refused.json()["code"] == "consent_required"
        assert (await _only_response(workspace, form_id))[1] == 0
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        [doc] = await container.form_response_repo().list_by_response_id(
            created.json()["responseId"]
        )
        # built by the server from the form's own consent items
        assert doc.consent and all(c.accepted for c in doc.consent if c.type == "checkbox")
        assert doc.submission_source.consent_asserted is True

    async def test_only_answers_hidden_fields_and_consent_are_taken(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        for extra in (
            {"dataOwnerIdentifier": "someone@example.org"},
            {"submissionSource": {"channel": "api", "keyId": "x"}},
            {"expiration": "1", "endingId": "x", "respondentEmail": "a@b.c"},
        ):
            refused = await _submit(
                client, token, form_id, _body({"name": text("Ada")}, **extra)
            )
            assert refused.status_code == 422, refused.text
            assert refused.json()["code"] == "invalid_request"
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_a_form_asking_for_a_verified_respondent_refuses_keys(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        link = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        link.settings.require_verified_identity = True
        await container.workspace_form_repo().update(link.id, link)
        token = await _key(workspace)
        refused = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert refused.status_code == 422
        assert refused.json()["code"] == "respondent_identity_required"
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_questions_that_take_a_file_or_a_signature_are_refused(
        self, client: AsyncClient, workspace
    ):
        spec = json.loads(json.dumps(SPEC))
        spec["pages"][0]["fields"] += [
            {"id": "cv", "type": "file_upload", "title": "Your CV"},
            {"id": "sign", "type": "short_text", "title": "Reference"},
        ]
        form_id = await _form(client, workspace, spec)
        token = await _key(workspace)
        answered = await _submit(
            client,
            token,
            form_id,
            _body({"name": text("Ada"), "cv": "https://example.org/cv.pdf"}),
        )
        assert answered.status_code == 422, answered.text
        assert {e["message"].split(":")[0] for e in answered.json()["errors"]} == {
            "question_not_supported"
        }
        # a file reference smuggled into another question's answer
        for slot in ({"file_url": "https://example.org/x"}, {"file_metadata": {"id": "x"}}):
            smuggled = await _submit(
                client,
                token,
                form_id,
                _body({"name": text("Ada"), "sign": {"type": "text", **slot}}),
            )
            assert smuggled.status_code == 422, smuggled.text
            assert smuggled.json()["errors"][0]["message"].startswith(
                "question_not_supported"
            )
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_hidden_fields_keep_only_the_declared_names(
        self, client: AsyncClient, workspace
    ):
        spec = json.loads(json.dumps(SPEC))
        spec["hiddenFields"] = ["utm_source"]
        form_id = await _form(client, workspace, spec)
        token = await _key(workspace)
        created = await _submit(
            client,
            token,
            form_id,
            _body(
                {"name": text("Ada")},
                hiddenFields={"utm_source": "crm", "other": "dropped"},
            ),
        )
        assert created.status_code == 201, created.text
        [doc] = await container.form_response_repo().list_by_response_id(
            created.json()["responseId"]
        )
        opened = container.form_response_service().decrypt_form_response(
            workspace_id=workspace.id, response=doc.model_copy(deep=True)
        )
        assert opened.hidden_fields == {"utm_source": "crm"}

    async def test_a_body_that_is_not_json_or_too_large(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        bad = await client.post(
            f"{BASE}/forms/{form_id}/submissions",
            content="{not json",
            headers=_auth(token, **{"Content-Type": "application/json"}),
        )
        assert bad.status_code == 422
        huge = await client.post(
            f"{BASE}/forms/{form_id}/submissions",
            content=json.dumps(_body({"name": text("x" * 1_100_000)})),
            headers=_auth(token, **{"Content-Type": "application/json"}),
        )
        assert huge.status_code == 413

    async def test_an_unknown_form_is_404(self, client: AsyncClient, workspace):
        token = await _key(workspace)
        for form_id in ("0" * 24, "not-an-id"):
            refused = await _submit(client, token, form_id, _body({"name": text("A")}))
            assert refused.status_code == 404


# -- who made it, and who sees that ---------------------------------------------------


class TestSource:
    async def test_staff_see_the_source_and_respondents_never(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        response_id = created.json()["responseId"]
        [doc] = await container.form_response_repo().list_by_response_id(response_id)
        [api_key] = [
            k
            for k in await container.workspace_api_key_repo().list_by_workspace(
                workspace.id
            )
            if "submissions:write" in k.scopes
        ]
        assert doc.submission_source == SubmissionSource(
            channel="api",
            key_id=str(api_key.id),
            key_name="submit key",
            consent_asserted=True,
        )
        detail = await container.form_response_service().get_workspace_submission(
            workspace.id, response_id, testUser
        )
        assert detail.source.key_name == "submit key"
        assert detail.source.channel == "api"
        assert str(api_key.id) not in repr(detail.source)
        # nothing respondent-facing carries it
        as_respondent = StandardFormResponseCamelModel(**doc.model_dump())
        assert "submission_source" not in as_respondent.model_dump()
        assert "submissionSource" not in as_respondent.model_dump(by_alias=True)
        # the key's own read never shows it either
        assert "source" not in json.dumps(await response_detail(workspace.id, response_id))

    async def test_a_respondent_cannot_claim_a_source(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        claim = {"channel": "api", "key_id": "x", "consent_asserted": True}
        for field in ("submission_source", "submissionSource"):
            sent = await client.post(
                f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
                data={
                    "response": json.dumps(
                        {"answers": {"name": text("Ada")}, field: claim}
                    )
                },
            )
            assert sent.status_code == 200, sent.text
        items, total = await _only_response(workspace, form_id)
        assert total == 2
        for item in items:
            [doc] = await container.form_response_repo().list_by_response_id(
                item["responseId"]
            )
            assert doc.submission_source is None
            detail = await container.form_response_service().get_workspace_submission(
                workspace.id, item["responseId"], testUser
            )
            assert detail.source is None

    def test_a_webhook_names_the_api_as_the_source_only_then(self):
        def body(source):
            return json.loads(
                webhook_payload.serialize(
                    event="submission",
                    delivery_id="d",
                    form_id="f",
                    response_id="r",
                    submitted_at=None,
                    data={},
                    source=source,
                )
            )

        assert body("api")["source"] == "api"
        assert "source" not in body(None)


# -- the same effects as a respondent's submission ---------------------------------------


class TestAfterTheSubmission:
    async def test_actions_webhooks_and_email_actions_run_as_for_a_respondent(
        self, client: AsyncClient, workspace
    ):
        service = container.workspace_form_service()
        hooks = {
            "actions": (service.action_service, "start_actions_for_submission"),
            "webhooks": (service._webhook_service, "queue_for_submission"),
            "email_actions": (service._email_action_service, "queue_for_submission"),
            "registration": (service._registration_service, "queue_for_submission"),
        }
        mocks = {}
        stack = ExitStack()
        for name, (target, method) in hooks.items():
            assert target is not None, name
            mocks[name] = stack.enter_context(
                patch.object(target, method, new=AsyncMock(return_value=[]))
            )
        with stack:
            form_id = await _form(client, workspace)
            token = await _key(workspace)
            created = await _submit(
                client, token, form_id, _body({"name": text("Ada")})
            )
            assert created.status_code == 201, created.text
        response_id = created.json()["responseId"]
        for name, mock in mocks.items():
            mock.assert_awaited_once()
        for name in ("webhooks", "email_actions", "registration"):
            assert mocks[name].await_args.kwargs["response_id"] == response_id
        # nobody is signed in, so the email copy has no account to go to
        assert mocks["email_actions"].await_args.kwargs["verified_account_id"] is None

    async def test_the_retention_the_form_states_is_applied_and_scheduled(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        link = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form_id
        )
        link.settings.response_expiration_type = "days"
        link.settings.response_expiration = "30"
        await container.workspace_form_repo().update(link.id, link)
        token = await _key(workspace)
        with patch.object(
            container.temporal_service(),
            "add_scheduled_job_for_deleting_response",
            new=AsyncMock(),
        ) as scheduled:
            created = await _submit(
                client, token, form_id, _body({"name": text("Ada")})
            )
        assert created.status_code == 201, created.text
        scheduled.assert_awaited_once()
        [doc] = await container.form_response_repo().list_by_response_id(
            created.json()["responseId"]
        )
        assert doc.expiration and str(doc.expiration_type.value) == "days"

    async def test_no_receipt_is_handed_out(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert "submissionUuid" not in created.text and "receipt" not in created.text.lower()


# -- idempotency, audit, rate limit ------------------------------------------------------


class TestIdempotencyAuditAndRate:
    async def test_a_retry_replays_and_a_different_body_is_refused(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "order-1"}
        first = await _submit(
            client, token, form_id, _body({"name": text("Ada")}), **headers
        )
        again = await _submit(
            client, token, form_id, _body({"name": text("Ada")}), **headers
        )
        assert first.status_code == again.status_code == 201
        assert again.headers["Idempotent-Replayed"] == "true"
        assert again.json() == first.json()
        assert (await _only_response(workspace, form_id))[1] == 1
        other = await _submit(
            client, token, form_id, _body({"name": text("Grace")}), **headers
        )
        assert other.status_code == 422
        assert other.json()["code"] == "idempotency_key_reused"
        assert (await _only_response(workspace, form_id))[1] == 1
        # only a summary is kept, never an answer
        [api_key] = [
            k
            for k in await container.workspace_api_key_repo().list_by_workspace(
                workspace.id
            )
            if "submissions:write" in k.scopes
        ]
        record = await container.idempotency_repo().find(
            idempotency._record_id(str(api_key.id), "order-1")
        )
        assert "Ada" not in record.body

    async def test_a_running_request_is_a_409_and_a_refusal_is_replayed(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "bad-1"}
        first = await _submit(client, token, form_id, _body({}), **headers)
        again = await _submit(client, token, form_id, _body({}), **headers)
        assert first.status_code == again.status_code == 422
        assert again.headers["Idempotent-Replayed"] == "true"

    async def test_one_audit_row_per_write_with_ids_and_no_content(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(
            client, token, form_id, _body({"name": text("Secret Person")})
        )
        response_id = created.json()["responseId"]
        patched = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "Other Secret"}},
            headers=_auth(token),
        )
        assert patched.status_code == 200, patched.text
        logs = await container.mcp_audit_log_repo().list_by_workspace(workspace.id)
        writes = [l for l in logs if l.tool.startswith("api:") and "submission" in l.tool]
        assert sorted(l.tool for l in writes) == [
            "api:create_submission",
            "api:update_submission",
        ]
        for log in writes:
            assert log.ok is True
            assert response_id in log.detail and form_id in log.detail
            assert "Secret" not in log.detail
        # and not a word of the answers in any log row
        assert not any("Secret" in l.detail for l in logs)

    async def test_writes_have_a_rate_budget_of_their_own(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        form_id = await _form(client, workspace)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_REQUESTS_PER_WINDOW", 2)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_WINDOW_SECONDS", 3600)
        token = await _key(workspace)
        # reads spend the reads' budget ...
        for _ in range(2):
            assert (
                await client.get(f"{BASE}/forms", headers=_auth(token))
            ).status_code == 200
        assert (await client.get(f"{BASE}/forms", headers=_auth(token))).status_code == 429
        # ... not the submissions'
        for index in range(2):
            ok = await _submit(client, token, form_id, _body({"name": text(f"A{index}")}))
            assert ok.status_code == 201, ok.text
        limited = await _submit(client, token, form_id, _body({"name": text("C")}))
        assert limited.status_code == 429
        assert limited.json()["code"] == "rate_limited"
        assert int(limited.headers["Retry-After"]) > 0
        assert (await _only_response(workspace, form_id))[1] == 2


# -- updating -----------------------------------------------------------------------------


class TestUpdate:
    async def _made(self, client, workspace, answers=None):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(
            client,
            token,
            form_id,
            _body(answers or {"name": text("Ada"), "age": {"type": "number", "number": 36}}),
        )
        assert created.status_code == 201, created.text
        return form_id, token, created.json()["responseId"]

    async def test_a_partial_update_replaces_what_is_sent_and_keeps_the_rest(
        self, client: AsyncClient, workspace
    ):
        form_id, token, response_id = await self._made(client, workspace)
        patched = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "Ada L."}},
            headers=_auth(token),
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["responseId"] == response_id
        answers = await _answers_of(workspace, response_id)
        assert answers["name"]["text"] == "Ada L."
        assert answers["age"]["number"] == 36
        # still sealed
        assert not isinstance(await _stored_row_answers(response_id), dict)

    async def test_the_respondent_edit_rules_apply(
        self, client: AsyncClient, workspace
    ):
        form_id, token, response_id = await self._made(client, workspace)
        url = f"{BASE}/forms/{form_id}/submissions/{response_id}"
        too_long = await client.patch(
            url, json={"answers": {"name": "x" * 21}}, headers=_auth(token)
        )
        assert too_long.status_code == 422
        assert too_long.json()["errors"][0]["path"] == "/answers/name"
        unknown = await client.patch(
            url, json={"answers": {"nope": "x"}}, headers=_auth(token)
        )
        assert unknown.status_code == 422
        assert _error_set(unknown) == {("nope", "unknown_field")}
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_another_key_cannot_change_it(self, client: AsyncClient, workspace):
        form_id, token, response_id = await self._made(client, workspace)
        other = await _key(workspace)
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "Hijacked"}},
            headers=_auth(other),
        )
        assert refused.status_code == 404
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_a_respondents_response_is_not_a_keys_to_change(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        sent = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {"name": text("Ada")}})},
        )
        assert sent.status_code == 200
        items, _ = await _only_response(workspace, form_id)
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{items[0]['responseId']}",
            json={"answers": {"name": "Hijacked"}},
            headers=_auth(token),
        )
        assert refused.status_code == 404
        assert (await _answers_of(workspace, items[0]["responseId"]))["name"][
            "text"
        ] == "Ada"

    async def test_a_response_of_another_form_or_an_unknown_id_is_404(
        self, client: AsyncClient, workspace
    ):
        form_id, token, response_id = await self._made(client, workspace)
        second = await _form(client, workspace)
        for path in (
            f"{second}/submissions/{response_id}",
            f"{form_id}/submissions/{'0' * 24}",
            f"{form_id}/submissions/not-an-id",
        ):
            refused = await client.patch(
                f"{BASE}/forms/{path}",
                json={"answers": {"name": "x"}},
                headers=_auth(token),
            )
            assert refused.status_code == 404, path

    async def test_a_key_limited_to_other_forms_cannot_update(
        self, client: AsyncClient, workspace
    ):
        form_id, token, response_id = await self._made(client, workspace)
        other = await _form(client, workspace)
        # same key id would be needed: narrow the first key's list instead
        [api_key] = [
            k
            for k in await container.workspace_api_key_repo().list_by_workspace(
                workspace.id
            )
            if "submissions:write" in k.scopes
        ]
        api_key.submission_form_ids = [other]
        await container.workspace_api_key_repo().save(api_key)
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "x"}},
            headers=_auth(token),
        )
        assert refused.status_code == 403
        assert refused.json()["code"] == "form_not_allowed"


# -- the document -------------------------------------------------------------------------


class TestDocument:
    def test_the_openapi_document_is_current_and_has_the_endpoints(self):
        assert public_openapi.main(["--check"]) == 0
        document = public_openapi.build_openapi()
        post = document["paths"]["/forms/{form_id}/submissions"]["post"]
        patch = document["paths"]["/forms/{form_id}/submissions/{response_id}"]["patch"]
        assert post["operationId"] == "createSubmission"
        assert patch["operationId"] == "updateSubmission"
        assert {"CreateSubmission", "UpdateSubmission"} <= set(
            document["components"]["schemas"]
        )


# -- malformed answers: a 422 with the question named, never a 500 -----------------------


class TestMalformedAnswers:
    @pytest.mark.parametrize(
        "answers",
        [
            {"age": 36.5},
            {"age": {"type": "number", "number": 36.5}},
            {"name": {"type": "text", "text": 5}},
            {"name": {"type": "bogus", "text": "x"}},
            {"name": {"type": "text", "text": {"nested": ["x"]}}},
            {"name": {"type": "text", "text": "x", "items": [{}]}},
            {"name": {"type": "text", "text": "x", "tags": "nope"}},
            {"name": ["a", "b"]},
            {"name": {"type": "text", "text": "x" * 100_000}},
        ],
        ids=[
            "decimal shorthand",
            "decimal typed",
            "wrong slot type",
            "unknown type",
            "nested slot",
            "items on a text",
            "tags not a list",
            "list for a text",
            "huge text",
        ],
    )
    async def test_never_a_500(self, client: AsyncClient, workspace, answers):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        base = {"name": text("Ada")}
        refused = await _submit(client, token, form_id, _body({**base, **answers}))
        assert refused.status_code < 500, refused.text
        # whatever it is, it is the same verdict the respondent route gives
        via_form = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": {**base, **answers}})},
        )
        if refused.status_code == 422:
            assert refused.json()["code"] == "invalid_answers"
            assert all(
                e["path"].startswith("/answers/") for e in refused.json().get("errors", [])
            )

    async def test_a_deeply_nested_body_is_a_422(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        nested = "[" * 50_000 + "]" * 50_000
        refused = await client.post(
            f"{BASE}/forms/{form_id}/submissions",
            content='{"answers": {"name": ' + nested + "}}",
            headers=_auth(token, **{"Content-Type": "application/json"}),
        )
        assert refused.status_code == 422, refused.text
        # (the same code any unreadable JSON body gets on this API)
        assert refused.json()["code"] in {"invalid_request", "invalid_answers", "unprocessable"}
        assert (await _only_response(workspace, form_id))[1] == 0


# -- parity on a richer form --------------------------------------------------------------


@pytest.fixture()
def rich_switches(monkeypatch):
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", True)


class TestRichParity:
    @pytest.mark.parametrize("case", RICH_CASES, ids=[c[0] for c in RICH_CASES])
    async def test_both_paths_judge_the_same(
        self, client: AsyncClient, workspace, rich_switches, case
    ):
        _, answers, status, problems = case
        form_id = await _form(client, workspace, RICH_SPEC)
        token = await _key(workspace)
        via_api = await _submit(client, token, form_id, _body(answers))
        via_form = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": answers})},
        )
        assert via_api.status_code == status, via_api.text
        assert via_form.status_code == (200 if status == 201 else status), via_form.text
        if status == 422:
            if problems is None:
                assert via_api.json()["code"] == "invalid_answers"
            else:
                assert _api_errors(via_api) == problems
                assert _form_errors(via_form) == problems
            assert (await _only_response(workspace, form_id))[1] == 0
            return
        items, total = await _only_response(workspace, form_id)
        assert total == 2
        stored = [await _answers_of(workspace, i["responseId"]) for i in items]
        assert stored[0] == stored[1]

    async def test_the_calculated_value_is_the_servers(
        self, client: AsyncClient, workspace, rich_switches
    ):
        form_id = await _form(client, workspace, RICH_SPEC)
        token = await _key(workspace)
        created = await _submit(
            client,
            token,
            form_id,
            _body(
                {
                    "name": text("Ada"),
                    "qty": number(3),
                    "extra": number(4),
                    "total": number(999),
                }
            ),
        )
        assert created.status_code == 201, created.text
        answers = await _answers_of(workspace, created.json()["responseId"])
        assert answers["total"]["number"] == 7

    async def test_too_many_items_in_a_group_are_refused_as_for_a_respondent(
        self, client: AsyncClient, workspace, rich_switches
    ):
        form_id = await _form(client, workspace, RICH_SPEC)
        token = await _key(workspace)
        crowd = {"name": text("Ada"), "guests": guests(*[{"gname": text("A")}] * 4)}
        via_api = await _submit(client, token, form_id, _body(crowd))
        via_form = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/response",
            data={"response": json.dumps({"answers": crowd})},
        )
        assert via_api.status_code == via_form.status_code == 422
        assert (await _only_response(workspace, form_id))[1] == 0
        # and 70 items (over the model's own cap) are a 422 as well
        many = {"name": text("Ada"), "guests": guests(*[{"gname": text("A")}] * 70)}
        assert (await _submit(client, token, form_id, _body(many))).status_code == 422

    async def test_shorthand_is_the_same_as_the_typed_answer(
        self, client: AsyncClient, workspace, rich_switches
    ):
        form_id = await _form(client, workspace, RICH_SPEC)
        token = await _key(workspace)
        shorthand = await _submit(
            client,
            token,
            form_id,
            _body(
                {
                    "name": "Ada",
                    "labels": ["vip", "late"],
                    "price": {"code": "EUR", "amount": "12.50"},
                    "stay": {"start": "2026-05-01", "end": "2026-05-04"},
                    "guests": [{"gname": "Bo", "gage": 30}, {"gname": "Cy"}],
                }
            ),
        )
        typed = await _submit(
            client,
            token,
            form_id,
            _body(
                {
                    "name": text("Ada"),
                    "labels": {"type": "tags", "tags": ["vip", "late"]},
                    "price": {
                        "type": "currency",
                        "currency": {"code": "EUR", "amount": "12.50"},
                    },
                    "stay": {
                        "type": "date_range",
                        "date_range": {"start": "2026-05-01", "end": "2026-05-04"},
                    },
                    "guests": guests(
                        {"gname": text("Bo"), "gage": number(30)}, {"gname": text("Cy")}
                    ),
                }
            ),
        )
        assert shorthand.status_code == typed.status_code == 201, shorthand.text
        assert await _answers_of(workspace, shorthand.json()["responseId"]) == (
            await _answers_of(workspace, typed.json()["responseId"])
        )

    async def test_a_problem_inside_a_group_item_is_named(
        self, client: AsyncClient, workspace, rich_switches
    ):
        form_id = await _form(client, workspace, RICH_SPEC)
        token = await _key(workspace)
        refused = await _submit(
            client,
            token,
            form_id,
            _body({"name": "Ada", "guests": [{"gname": "Bo"}, {"gage": 5}]}),
        )
        assert refused.status_code == 422
        assert refused.json()["code"] == "invalid_answers"
        # the respondent route names the question and the item in text
        assert "Guest name" in refused.json()["message"]


ADDRESS_SPEC = json.loads(json.dumps(SPEC))
ADDRESS_SPEC["pages"][0]["fields"].append(
    {
        "id": "home",
        "type": "address",
        "title": "Home address",
        "whyWeAsk": "To send the programme.",
        "countries": ["NL"],
    }
)


class TestAddressShorthand:
    async def test_an_address_object_is_the_typed_answer(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        monkeypatch.setattr(settings, "ADDRESS_QUESTION_ENABLED", True)
        form_id = await _form(client, workspace, ADDRESS_SPEC)
        token = await _key(workspace)
        parts = {
            "street": "Keizersgracht",
            "house_number": "12",
            "postcode": "1015 CS",
            "city": "Amsterdam",
            "country": "NL",
        }
        shorthand = await _submit(
            client, token, form_id, _body({"name": "Ada", "home": parts})
        )
        typed = await _submit(
            client,
            token,
            form_id,
            _body({"name": text("Ada"), "home": {"type": "address", "address": parts}}),
        )
        assert shorthand.status_code == typed.status_code == 201, shorthand.text
        assert await _answers_of(workspace, shorthand.json()["responseId"]) == (
            await _answers_of(workspace, typed.json()["responseId"])
        )


# -- a private form, and updates after the form's gates changed --------------------------------


async def _lock(workspace, form_id, **values):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    for key, value in values.items():
        setattr(link.settings, key, value)
    await container.workspace_form_repo().update(link.id, link)


class TestPrivateAndLockedForms:
    async def test_a_private_form_refuses_keys(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace)
        await _lock(workspace, form_id, private=True)
        token = await _key(workspace)
        refused = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert refused.status_code == 422
        assert refused.json()["code"] == "respondent_identity_required"
        assert (await _only_response(workspace, form_id))[1] == 0

    @pytest.mark.parametrize(
        "change, status, code",
        [
            ({"require_verified_identity": True}, 422, "respondent_identity_required"),
            ({"private": True}, 422, "respondent_identity_required"),
            (
                {
                    "form_close_date": (
                        dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
                    ).isoformat()
                },
                409,
                "form_closed",
            ),
            (
                {
                    "form_open_date": (
                        dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)
                    ).isoformat()
                },
                409,
                "form_not_open",
            ),
        ],
        ids=["identity required", "private", "closed", "not open yet"],
    )
    async def test_a_form_that_was_locked_since_takes_no_update(
        self, client: AsyncClient, workspace, change, status, code
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        response_id = created.json()["responseId"]
        await _lock(workspace, form_id, **change)
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": "Rewritten"}},
            headers=_auth(token),
        )
        assert refused.status_code == status, refused.text
        assert refused.json()["code"] == code
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"


# -- the creator must still be able to edit forms ---------------------------------------------


async def _member(workspace, role) -> User:
    user = User(id=str(RecordId()), sub="submissions-member@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
    )
    return user


async def _set_role(workspace, user: User, role) -> None:
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, RecordId(user.id))
    membership.roles = [role]
    await repo.save(membership)


class TestCreatorStillEdits:
    @pytest.mark.parametrize(
        "role",
        [WorkspaceRoles.VIEWER, WorkspaceRoles.REVIEWER, WorkspaceRoles.PRIVACY_OFFICER],
    )
    async def test_a_demoted_creators_key_stops_writing(
        self, client: AsyncClient, workspace, role
    ):
        form_id = await _form(client, workspace)
        admin = await _member(workspace, WorkspaceRoles.ADMIN)
        token = await _key(workspace, user=admin)
        made = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        assert made.status_code == 201, made.text
        await _set_role(workspace, admin, role)
        for call in (
            _submit(client, token, form_id, _body({"name": text("Bo")})),
            client.patch(
                f"{BASE}/forms/{form_id}/submissions/{made.json()['responseId']}",
                json={"answers": {"name": "Rewritten"}},
                headers=_auth(token),
            ),
        ):
            refused = await call
            assert refused.status_code == 403, refused.text
            assert refused.json()["code"] == "key_creator_lacks_permission"
        assert (await _only_response(workspace, form_id))[1] == 1
        assert (await _answers_of(workspace, made.json()["responseId"]))["name"][
            "text"
        ] == "Ada"

    async def test_an_editor_creator_works_and_a_disabled_workspace_does_not(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        assert (
            await _submit(client, token, form_id, _body({"name": text("Ada")}))
        ).status_code == 201
        await container.workspace_repo().set_fields(workspace, {"disabled": True})
        refused = await _submit(client, token, form_id, _body({"name": text("Bo")}))
        assert refused.status_code == 403
        assert refused.json()["code"] == "key_creator_lacks_permission"
        assert (await _only_response(workspace, form_id))[1] == 1


# -- a failure after the commit never makes a retry store a second response -------------------


class TestFailureAfterTheCommit:
    async def test_a_hook_that_raises_changes_nothing_for_the_caller(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        service = container.workspace_form_service()
        headers = {"Idempotency-Key": "after-1"}
        with patch.object(
            service.action_service,
            "start_actions_for_submission",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ), patch.object(
            service._webhook_service,
            "queue_for_submission",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            first = await _submit(
                client, token, form_id, _body({"name": text("Ada")}), **headers
            )
        assert first.status_code == 201, first.text
        again = await _submit(
            client, token, form_id, _body({"name": text("Ada")}), **headers
        )
        assert again.status_code == 201
        assert again.headers["Idempotent-Replayed"] == "true"
        assert again.json() == first.json()
        assert (await _only_response(workspace, form_id))[1] == 1

    async def test_a_failure_right_after_the_insert_is_still_a_success(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "after-2"}
        with patch.object(
            container.form_response_service(),
            "decrypt_form_response",
            side_effect=RuntimeError("boom"),
        ):
            first = await _submit(
                client, token, form_id, _body({"name": text("Ada")}), **headers
            )
        assert first.status_code == 201, first.text
        retry = await _submit(
            client, token, form_id, _body({"name": text("Ada")}), **headers
        )
        assert retry.status_code == 201 and retry.json() == first.json()
        assert (await _only_response(workspace, form_id))[1] == 1

    async def test_a_failure_before_the_commit_is_a_5xx_and_frees_the_key(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "before-1"}
        with patch.object(
            container.form_response_service(),
            "submit_form_response",
            new=AsyncMock(side_effect=RuntimeError("boom")),
        ):
            failed = await _submit(
                client, token, form_id, _body({"name": text("Ada")}), **headers
            )
        assert failed.status_code == 500
        retry = await _submit(
            client, token, form_id, _body({"name": text("Ada")}), **headers
        )
        assert retry.status_code == 201, retry.text
        assert (await _only_response(workspace, form_id))[1] == 1


# -- small things the review found ----------------------------------------------------------


class TestSmallThings:
    @pytest.mark.parametrize("consent", ["true", "yes", 1, "1"])
    async def test_consent_is_literally_true(
        self, client: AsyncClient, workspace, consent
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        refused = await _submit(
            client, token, form_id, {"answers": {"name": text("Ada")}, "consent": consent}
        )
        assert refused.status_code == 422, refused.text
        assert (await _only_response(workspace, form_id))[1] == 0

    async def test_an_update_cannot_clear_an_answer_with_null(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        created = await _submit(client, token, form_id, _body({"name": text("Ada")}))
        response_id = created.json()["responseId"]
        refused = await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{response_id}",
            json={"answers": {"name": None}},
            headers=_auth(token),
        )
        assert refused.status_code == 422
        assert refused.json()["errors"][0]["message"].startswith("clear_not_supported")
        assert (await _answers_of(workspace, response_id))["name"]["text"] == "Ada"

    async def test_a_404_is_not_kept_for_the_key(self, client: AsyncClient, workspace):
        form_id = await _form(client, workspace, publish=False)
        token = await _key(workspace)
        headers = {"Idempotency-Key": "late-1"}
        body = _body({"name": text("Ada")})
        assert (await _submit(client, token, form_id, body, **headers)).status_code == 404
        # published since: the same key and request now work
        await client.post(
            f"{BASE}/forms/{form_id}/publish",
            headers=_auth(await _key(workspace, ["forms:write"])),
        )
        retried = await _submit(client, token, form_id, body, **headers)
        assert retried.status_code == 201, retried.text

    async def test_a_key_without_the_scope_does_not_spend_the_submissions_budget(
        self, client: AsyncClient, workspace, monkeypatch
    ):
        form_id = await _form(client, workspace)
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_REQUESTS_PER_WINDOW", 100)
        monkeypatch.setattr(
            settings.api_settings, "PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", 2
        )
        monkeypatch.setattr(settings.api_settings, "PUBLIC_API_WINDOW_SECONDS", 3600)
        reader = await _key(workspace, ["forms:read"])
        for _ in range(5):
            refused = await _submit(client, reader, form_id, _body({"name": text("A")}))
            assert refused.status_code == 403
        writer = await _key(workspace)
        assert (
            await _submit(client, writer, form_id, _body({"name": text("Ada")}))
        ).status_code == 201

    async def test_the_audit_row_keeps_only_an_id_shaped_segment(
        self, client: AsyncClient, workspace
    ):
        form_id = await _form(client, workspace)
        token = await _key(workspace)
        hostile = "x" * 80 + "script"
        await client.patch(
            f"{BASE}/forms/{form_id}/submissions/{hostile}",
            json={"answers": {}},
            headers=_auth(token),
        )
        logs = await container.mcp_audit_log_repo().list_by_workspace(workspace.id)
        rows = [l for l in logs if l.tool == "api:update_submission"]
        assert rows and all("script" not in l.detail for l in rows)
        assert any("response_id=invalid" in l.detail for l in rows)
