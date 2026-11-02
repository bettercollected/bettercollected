"""The executor holds no key: the backend hands over a run's secrets opened when
the executor asks (``{"secrets": "plain"}``), and takes a refreshed credential
back in plain, on the run's own route, to seal it. An older executor, which asks
for nothing, gets what it always got."""

import json
import time

import pytest
from common.models.standard_form import ParameterValue

from backend.app.container import container
from backend.app.services.action_run_token import HEADER, TTL_SECONDS, run_token
from backend.config import settings
from tests.app.jobs.test_action_runs import (  # noqa: F401 - fixtures and helpers
    ANSWER,
    JOB_KEY,
    _ask,
    _context_url,
    _queued_token,
    _set_status,
    _submitted,
    job_key,
    memory_jobs,
)
from tests.app.services.test_action_secrets import (  # noqa: F401 - fixtures
    configured_form,
    partner_action,
)

FORM_CRED = "form-credential-in-plain"
WORKSPACE_CRED = "workspace-credential-in-plain"
ACTION_SECRET = "global-secret"  # partner_action's own, sealed when it is stored


def sealed(value):
    return container.crypto().encrypt(value)


async def _seal_credentials(workspace, form, action):
    """The form's and the workspace's credentials as the app stores them: sealed."""
    action_id = str(action.id)
    stored = await container.form_repo().get_form_document_by_id(form.form_id)
    stored.secrets = {
        action_id: [ParameterValue(name="Credentials", value=sealed(FORM_CRED))]
    }
    await container.form_repo().save_form(stored)
    await container.action_repository().create_action_in_workspace_from_action(
        workspace_id=workspace.id,
        action_id=action.id,
        credentials=sealed(WORKSPACE_CRED),
    )


def _ask_for(client, workspace, form, action, response_id, body):
    token = _queued_token(workspace, form, action, response_id) or run_token(
        workspace.id, form.form_id, action.id, response_id
    )
    return client.post(
        _context_url(workspace, form, action, response_id),
        headers={"api-key": JOB_KEY, HEADER: token},
        json=body,
    )


class TestSecretsOpenedForTheExecutor:
    async def test_asked_for_plain_the_secrets_come_opened(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)

        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "plain"},
        )

        assert got.status_code == 200, got.text
        body = got.json()
        assert body["secrets_plain"] is True
        action_id = str(partner_action.id)
        assert json.loads(body["action"])["secrets"][0]["value"] == ACTION_SECRET
        assert json.loads(body["form"])["secrets"][action_id][0]["value"] == FORM_CRED
        assert (
            json.loads(body["workspace"])["secrets"][action_id][0]["value"]
            == WORKSPACE_CRED
        )

    async def test_an_executor_that_asks_for_nothing_gets_them_sealed(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)

        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )

        body = got.json()
        assert "secrets_plain" not in body
        text = json.dumps(body)
        for plain in (FORM_CRED, WORKSPACE_CRED, ACTION_SECRET):
            assert plain not in text
        action_id = str(partner_action.id)
        form = json.loads(body["form"])
        assert container.crypto().decrypt(form["secrets"][action_id][0]["value"]) == (
            FORM_CRED
        )

    async def test_asking_for_sealed_is_the_default(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "sealed"},
        )
        assert got.status_code == 200 and "secrets_plain" not in got.json()

    async def test_the_hand_out_is_logged_with_ids_and_a_count_never_a_value(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        from loguru import logger

        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        lines = []
        sink = logger.add(lambda m: lines.append(str(m)), level="INFO")
        try:
            got = await _ask_for(
                client,
                workspace,
                configured_form,
                partner_action,
                response.response_id,
                {"secrets": "plain"},
            )
        finally:
            logger.remove(sink)
        assert got.status_code == 200
        text = "".join(lines)
        assert "run secrets handed to the executor opened" in text
        assert response.response_id in text and str(partner_action.id) in text
        assert "count=3" in text  # the action's own, the form's and the workspace's
        for value in (FORM_CRED, WORKSPACE_CRED, ACTION_SECRET, ANSWER):
            assert value not in text

    @pytest.mark.parametrize("body", [{"secrets": "everything"}, {"secrets": 1}])
    async def test_an_unknown_request_is_refused(
        self, client, workspace, configured_form, partner_action, memory_jobs, body
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            body,
        )
        assert got.status_code == 422

    async def test_plain_needs_the_runs_token_like_everything_else(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await client.post(
            _context_url(
                workspace, configured_form, partner_action, response.response_id
            ),
            headers={"api-key": JOB_KEY, HEADER: "0" * 64},
            json={"secrets": "plain"},
        )
        assert got.status_code == 403
        assert FORM_CRED not in got.text and ANSWER not in got.text

    async def test_a_secret_no_key_opens_fails_the_run_and_leaks_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        # the fixture's form credential is not sealed with this deployment's key
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "plain"},
        )
        assert got.status_code == 500
        assert "encrypted-cred-value" not in got.text and ANSWER not in got.text


def _write_url(workspace, form, action, response_id):
    return _context_url(workspace, form, action, response_id).replace(
        "/context", "/secrets"
    )


def _write(
    client, workspace, form, action, response_id, token=None, key=JOB_KEY, **payload
):
    if token is None:
        token = _queued_token(workspace, form, action, response_id) or run_token(
            workspace.id, form.form_id, action.id, response_id
        )
    body = {"name": "Credentials", "value": '{"token": "refreshed"}', "type": "secrets"}
    body.update(payload)
    return client.patch(
        _write_url(workspace, form, action, response_id),
        headers={"api-key": key, HEADER: token},
        json=body,
    )


async def _stored_credentials(form_id, action):
    form = await container.form_repo().get_form_document_by_id(form_id)
    return {s.name: s.value for s in form.secrets[str(action.id)]}


class TestTheRefreshedCredentialGoesBackInPlain:
    async def test_it_is_sealed_with_the_backends_key(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)

        got = await _write(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 200, got.text
        stored = await _stored_credentials(configured_form.form_id, partner_action)
        assert '"refreshed"' not in stored["Credentials"]  # not stored in plain
        assert container.crypto().decrypt(stored["Credentials"]) == (
            '{"token": "refreshed"}'
        )

    async def test_the_job_key_alone_writes_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)

        for token in ("", "0" * 64):
            got = await client.patch(
                _write_url(
                    workspace, configured_form, partner_action, response.response_id
                ),
                headers={"api-key": JOB_KEY, HEADER: token},
                json={"name": "Credentials", "value": "x", "type": "secrets"},
            )
            assert got.status_code == 403
        got = await _write(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            key="wrong",
        )
        assert got.status_code == 403
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_a_run_that_is_over_writes_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)
        token = job["args"]["run_token"]
        _set_status(memory_jobs, job, "succeeded")

        got = await _write(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=token,
        )

        assert got.status_code == 403
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_one_runs_token_writes_no_other_runs_form(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        token = job["args"]["run_token"]
        other_form = "0" * 24
        got = await client.patch(
            _write_url(
                workspace, configured_form, partner_action, response.response_id
            ).replace(configured_form.form_id, other_form),
            headers={"api-key": JOB_KEY, HEADER: token},
            json={"name": "Credentials", "value": "x", "type": "secrets"},
        )
        assert got.status_code == 403

    async def test_a_secret_the_action_does_not_hold_is_not_created(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        # the form's action holds a Token and no Credentials
        action_id = str(partner_action.id)
        stored = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        stored.secrets = {action_id: [ParameterValue(name="Token", value=sealed("t"))]}
        await container.form_repo().save_form(stored)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)

        got = await _write(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 200
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )
        assert "Credentials" not in before

    @pytest.mark.parametrize("name", ["Token", "Another", "credentials", "Password"])
    async def test_only_the_credential_can_be_written(
        self, client, workspace, configured_form, partner_action, memory_jobs, name
    ):
        # even a secret the action holds is not the executor's to replace
        await _seal_credentials(workspace, configured_form, partner_action)
        action_id = str(partner_action.id)
        stored = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        stored.secrets[action_id].append(
            ParameterValue(name=name, value=sealed("keep"))
        )
        await container.form_repo().save_form(stored)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)

        got = await _write(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            name=name,
        )

        assert got.status_code == 422
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_a_switched_off_action_is_gone(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        from common.models.standard_form import ActionState

        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)
        form = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        form.actions = {"on_submit": [ActionState(id=partner_action.id, enabled=False)]}
        await container.form_repo().save_form(form)

        got = await _write(
            client, workspace, configured_form, partner_action, response.response_id
        )

        assert got.status_code == 410
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    @pytest.mark.parametrize(
        "payload",
        [{"value": ""}, {"value": "x" * (64 * 1024 + 1)}, {"name": ""}],
    )
    async def test_an_empty_or_huge_value_is_refused(
        self, client, workspace, configured_form, partner_action, memory_jobs, payload
    ):
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _write(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            **payload,
        )
        assert got.status_code == 422


# ---- what the release hardening adds ------------------------------------------------

OTHER_ACTION = "65b0000000000000000000aa"
OTHER_SECRET = "SECRET-OF-ANOTHER-ACTION-IN-PLAIN"


def _key_only_url(form, action):
    return f"/api/v1/temporal/forms/{form.form_id}/actions/{action.id}/secrets"


def _key_only(client, form, action, **payload):
    body = {"name": "Credentials", "value": sealed('{"token": "old"}'), "type": "secrets"}
    body.update(payload)
    return client.patch(
        _key_only_url(form, action), headers={"api-key": JOB_KEY}, json=body
    )


@pytest.fixture
def sealed_off(monkeypatch):
    """The 4.3 deploy: ``ACTION_SECRETS_SEALED_ALLOWED`` turned off."""
    monkeypatch.setattr(settings, "ACTION_SECRETS_SEALED_ALLOWED", False)


class TestSealedModeCanBeSwitchedOff:
    async def test_it_is_allowed_by_default_for_executors_that_are_not_upgraded(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        assert settings.ACTION_SECRETS_SEALED_ALLOWED is True
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )
        assert got.status_code == 200 and "secrets_plain" not in got.json()
        written = await _key_only(client, configured_form, partner_action)
        assert written.status_code == 200

    @pytest.mark.parametrize("body", [None, {"secrets": "sealed"}])
    async def test_off_a_sealed_context_is_refused_loudly_and_hands_out_nothing(
        self,
        client,
        workspace,
        configured_form,
        partner_action,
        memory_jobs,
        sealed_off,
        body,
    ):
        from loguru import logger

        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        lines = []
        sink = logger.add(lambda m: lines.append(str(m)), level="ERROR")
        try:
            if body is None:
                got = await _ask(
                    client,
                    workspace,
                    configured_form,
                    partner_action,
                    response.response_id,
                )
            else:
                got = await _ask_for(
                    client,
                    workspace,
                    configured_form,
                    partner_action,
                    response.response_id,
                    body,
                )
        finally:
            logger.remove(sink)

        assert got.status_code == 426
        assert "AES_HEX_KEY" in got.text and "ACTION_SECRETS_SEALED_ALLOWED" in got.text
        for value in (FORM_CRED, WORKSPACE_CRED, ANSWER, ACTION_SECRET):
            assert value not in got.text
        assert "ACTION_SECRETS_SEALED_ALLOWED is off" in "".join(lines)
        assert got.headers["cache-control"] == "no-store"

    async def test_off_an_executor_of_4_3_asking_for_plain_is_served(
        self,
        client,
        workspace,
        configured_form,
        partner_action,
        memory_jobs,
        sealed_off,
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "plain"},
        )
        assert got.status_code == 200 and got.json()["secrets_plain"] is True

    async def test_off_the_refusal_comes_after_the_run_is_authorised(
        self, client, workspace, configured_form, partner_action, memory_jobs, sealed_off
    ):
        # a caller that cannot prove a run learns nothing about the setting
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _ask(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token="0" * 64,
        )
        assert got.status_code == 403

    async def test_off_the_key_only_write_back_is_refused_and_writes_nothing(
        self, client, workspace, configured_form, partner_action, sealed_off
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        before = await _stored_credentials(configured_form.form_id, partner_action)

        got = await _key_only(client, configured_form, partner_action)

        assert got.status_code == 426
        assert "ACTION_SECRETS_SEALED_ALLOWED" in got.text
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_off_the_run_scoped_write_back_still_works(
        self,
        client,
        workspace,
        configured_form,
        partner_action,
        memory_jobs,
        sealed_off,
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _write(
            client, workspace, configured_form, partner_action, response.response_id
        )
        assert got.status_code == 200


class TestTheKeyOnlyRouteReplacesTheCredentialAndNothingElse:
    @pytest.mark.parametrize("name", ["Token", "Another", "credentials", "Password"])
    async def test_a_secret_under_another_name_is_refused(
        self, client, workspace, configured_form, partner_action, name
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        action_id = str(partner_action.id)
        stored = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        stored.secrets[action_id].append(
            ParameterValue(name=name, value=sealed("keep"))
        )
        await container.form_repo().save_form(stored)
        before = await _stored_credentials(configured_form.form_id, partner_action)

        # ciphertext the caller has seen (the stored one) replayed into that secret
        got = await _key_only(
            client, configured_form, partner_action, name=name, value=before[name]
        )

        assert got.status_code == 422
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_the_credential_is_replaced_and_the_answer_has_no_cache(
        self, client, workspace, configured_form, partner_action
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        got = await _key_only(client, configured_form, partner_action)
        assert got.status_code == 200
        assert got.headers["cache-control"] == "no-store"
        stored = await _stored_credentials(configured_form.form_id, partner_action)
        assert container.crypto().decrypt(stored["Credentials"]) == '{"token": "old"}'


class TestPlainWithoutAKeyFailsClosed:
    async def test_plain_with_no_key_is_503_and_never_sealed_or_empty(
        self, client, workspace, configured_form, partner_action, memory_jobs, monkeypatch
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        monkeypatch.setattr(container.action_service(), "crypto", None)

        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "plain"},
        )

        assert got.status_code == 503
        for value in (FORM_CRED, WORKSPACE_CRED, ANSWER, ACTION_SECRET):
            assert value not in got.text
        assert "secrets_plain" not in got.text and "action" not in got.json()

    async def test_sealed_with_no_key_is_still_what_it_was(
        self, client, workspace, configured_form, partner_action, memory_jobs, monkeypatch
    ):
        # the refusal is for plain: a sealed hand-out needs no key here
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        monkeypatch.setattr(container.action_service(), "crypto", None)
        got = await _ask(
            client, workspace, configured_form, partner_action, response.response_id
        )
        assert got.status_code == 200 and "secrets_plain" not in got.json()


class TestPlainNeverCarriesAnotherActionsSecrets:
    async def test_the_secrets_of_the_forms_other_actions_stay_in_the_backend(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        action_id = str(partner_action.id)
        stored = await container.form_repo().get_form_document_by_id(
            configured_form.form_id
        )
        stored.secrets[OTHER_ACTION] = [
            ParameterValue(name="Credentials", value=sealed(OTHER_SECRET))
        ]
        await container.form_repo().save_form(stored)
        await container.action_repository().create_action_in_workspace_from_action(
            workspace_id=workspace.id,
            action_id=partner_action.id,
            credentials=sealed(WORKSPACE_CRED),
        )
        response, _ = await _submitted(workspace, configured_form, memory_jobs)

        got = await _ask_for(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            {"secrets": "plain"},
        )

        assert got.status_code == 200, got.text
        body = got.json()
        assert OTHER_SECRET not in got.text
        assert OTHER_ACTION not in json.dumps(json.loads(body["form"])["secrets"])
        assert list(json.loads(body["form"])["secrets"]) == [action_id]
        assert got.headers["cache-control"] == "no-store"


class TestTheWriteBackIsBoundToItsRun:
    async def test_another_workspace_or_another_action_is_refused(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, job = await _submitted(workspace, configured_form, memory_jobs)
        token = job["args"]["run_token"]
        before = await _stored_credentials(configured_form.form_id, partner_action)
        url = _write_url(
            workspace, configured_form, partner_action, response.response_id
        )
        other_workspace = url.replace(str(workspace.id), "0" * 24)
        other_action = url.replace(str(partner_action.id), OTHER_ACTION)

        for refused_url in (other_workspace, other_action):
            got = await client.patch(
                refused_url,
                headers={"api-key": JOB_KEY, HEADER: token},
                json={"name": "Credentials", "value": "x", "type": "secrets"},
            )
            assert got.status_code == 403
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_an_expired_run_token_writes_nothing_and_reads_nothing(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        before = await _stored_credentials(configured_form.form_id, partner_action)
        old = run_token(
            workspace.id,
            configured_form.form_id,
            partner_action.id,
            response.response_id,
            now=time.time() - 2 * TTL_SECONDS,
        )

        written = await _write(
            client,
            workspace,
            configured_form,
            partner_action,
            response.response_id,
            token=old,
        )
        read = await client.post(
            _context_url(
                workspace, configured_form, partner_action, response.response_id
            ),
            headers={"api-key": JOB_KEY, HEADER: old},
            json={"secrets": "plain"},
        )

        assert written.status_code == 410 and read.status_code == 410
        assert FORM_CRED not in read.text
        assert (
            await _stored_credentials(configured_form.form_id, partner_action) == before
        )

    async def test_the_write_back_answer_is_not_cached(
        self, client, workspace, configured_form, partner_action, memory_jobs
    ):
        await _seal_credentials(workspace, configured_form, partner_action)
        response, _ = await _submitted(workspace, configured_form, memory_jobs)
        got = await _write(
            client, workspace, configured_form, partner_action, response.response_id
        )
        assert got.status_code == 200
        assert got.headers["cache-control"] == "no-store"
