"""Setting a form's language: the set_form_language op, the builder's save,
the form spec, and publishing.

The language is the form's own setting (``StandardFormSettings.language``),
not one of the workspace's settings for the form: the op writes the form,
the builder's whole-form save sends it alone and keeps the form's other
settings, and a publish carries it into the live version, also when it is
the only change."""

import copy
import json
from unittest.mock import AsyncMock, patch

import pytest
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import parse_ops
from backend.app.services.form_service import FormService
from tests.app.controllers.data import testUser
from tests.app.controllers.test_public_api import BASE, SPEC, _auth, _create, _token


@pytest.fixture()
def user_details():
    """The draft read asks the auth service for the importer's details."""
    with patch.object(
        FormService,
        "fetch_user_details",
        AsyncMock(return_value={"users_info": [{"_id": testUser.id}]}),
    ):
        yield


def _forms_url(workspace, form_id):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form_id}"


def _body(settings=None):
    body = {
        "title": "Taal",
        "builderVersion": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "layout": "SINGLE_COLUMN_NO_BACKGROUND",
                    "fields": [
                        {"id": "naam", "index": 0, "type": "short_text", "title": "Naam"}
                    ],
                },
            }
        ],
        "thankyouPage": [{"layout": "SINGLE_COLUMN_NO_BACKGROUND"}],
    }
    if settings is not None:
        body["settings"] = settings
    return body


async def _save(client, workspace, form_id, cookies, settings=None):
    reply = await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(_body(settings))},
        cookies=cookies,
    )
    assert reply.status_code == 200, reply.text
    return reply


async def _draft(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


async def _set_language(workspace, form_id, language):
    """The op through the one write path every ops writer uses."""
    document = await _draft(form_id)
    form = StandardForm(**document.model_dump())
    _, results, settings = await persist_ops_to_form(
        document,
        form,
        parse_ops([{"op": "set_form_language", "language": language}]),
        workspace_id=workspace.id,
        atomic=True,
    )
    return results, settings


async def _publish(workspace, form_id):
    return await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )


async def _live_language(client, workspace, form_id):
    live = await client.get(_forms_url(workspace, form_id), params={"published": True})
    assert live.status_code == 200, live.text
    return live.json()["settings"].get("language")


async def test_the_op_writes_the_forms_own_language(
    client: AsyncClient, workspace, workspace_form, test_user_cookies, user_details
):
    form_id = workspace_form.form_id
    await _save(client, workspace, form_id, test_user_cookies)

    results, settings = await _set_language(workspace, form_id, "NL")
    assert [r.ok for r in results] == [True]
    assert results[0].message == "Set the form's language to Nederlands (nl)"
    # not a workspace setting: nothing written there
    assert settings is None
    assert (await _draft(form_id)).settings.language == "nl"
    association = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form_id
    )
    assert "language" not in association.settings.model_dump()

    draft = await client.get(_forms_url(workspace, form_id), cookies=test_user_cookies)
    assert draft.status_code == 200, draft.text
    assert draft.json()["settings"]["language"] == "nl"


async def test_an_unknown_language_changes_nothing(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    await _save(client, workspace, form_id, test_user_cookies, {"language": "fr"})
    before = (await _draft(form_id)).updated_at

    results, _ = await _set_language(workspace, form_id, "klingon")
    assert results[0].ok is False
    assert "is not a language a form can be set to" in results[0].message
    stored = await _draft(form_id)
    assert stored.settings.language == "fr" and stored.updated_at == before


async def test_publishing_takes_the_language_live_even_when_it_is_the_only_change(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    await _save(client, workspace, form_id, test_user_cookies)
    first = await _publish(workspace, form_id)
    assert await _live_language(client, workspace, form_id) is None

    await _set_language(workspace, form_id, "de")
    # the draft's language waits for the next publish
    assert await _live_language(client, workspace, form_id) is None
    second = await _publish(workspace, form_id)
    assert second.version == first.version + 1
    assert await _live_language(client, workspace, form_id) == "de"

    await _set_language(workspace, form_id, None)
    assert (await _draft(form_id)).settings.language is None
    third = await _publish(workspace, form_id)
    assert third.version == second.version + 1
    assert await _live_language(client, workspace, form_id) is None

    # nothing changed: no new version
    assert (await _publish(workspace, form_id)).version == third.version


async def test_a_builder_save_sends_the_language_and_keeps_the_other_settings(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    document = await _draft(form_id)
    document.settings.embed_url = "https://embed.example/form"
    await container.form_repo().save_form(document)

    await _save(client, workspace, form_id, test_user_cookies, {"language": "sv"})
    stored = await _draft(form_id)
    assert stored.settings.language == "sv"
    assert stored.settings.embed_url == "https://embed.example/form"

    # a save without settings (an older builder) keeps the language
    await _save(client, workspace, form_id, test_user_cookies)
    assert (await _draft(form_id)).settings.language == "sv"

    # the builder clears it by sending none
    await _save(client, workspace, form_id, test_user_cookies, {"language": None})
    stored = await _draft(form_id)
    assert stored.settings.language is None
    assert stored.settings.embed_url == "https://embed.example/form"


async def test_a_builder_save_takes_only_a_listed_language(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    refused = await client.patch(
        _forms_url(workspace, form_id),
        data={"form_body": json.dumps(_body({"language": "tlh"}))},
        cookies=test_user_cookies,
    )
    assert refused.status_code == 422, refused.text
    assert "is not a language a form can be set to" in refused.text

    # a language an import set, sent back unchanged, is kept as it is
    document = await _draft(form_id)
    document.settings.language = "en-GB"
    await container.form_repo().save_form(document)
    await _save(client, workspace, form_id, test_user_cookies, {"language": "en-GB"})
    assert (await _draft(form_id)).settings.language == "en-GB"

    # a listed one in another case is stored as the op stores it
    await _save(client, workspace, form_id, test_user_cookies, {"language": "NL"})
    assert (await _draft(form_id)).settings.language == "nl"


async def test_a_builder_save_of_the_language_leaves_the_workspace_settings(
    client: AsyncClient, workspace, workspace_form, test_user_cookies
):
    form_id = workspace_form.form_id
    repo = container.workspace_form_repo()
    association = await repo.find_workspace_form(workspace.id, form_id)
    association.settings.purpose = "To plan."
    await repo.save(association)

    await _save(client, workspace, form_id, test_user_cookies, {"language": "nl"})
    association = await repo.find_workspace_form(workspace.id, form_id)
    assert association.settings.purpose == "To plan."
    assert "language" not in association.settings.model_dump()


class TestTheFormSpec:
    async def test_a_document_sets_reads_keeps_and_clears_the_language(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token, dict(copy.deepcopy(SPEC), language="nl"))
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        assert created.json()["form"]["language"] == "nl"
        assert (await _draft(form_id)).settings.language == "nl"

        # left out of a replacement: kept
        kept = await client.put(
            f"{BASE}/forms/{form_id}",
            json=copy.deepcopy(SPEC),
            headers=_auth(token, **{"If-Match": etag}),
        )
        assert kept.status_code == 200, kept.text
        assert kept.json()["language"] == "nl"

        # null: cleared
        cleared = await client.put(
            f"{BASE}/forms/{form_id}",
            json=dict(copy.deepcopy(SPEC), language=None),
            headers=_auth(token, **{"If-Match": kept.headers["ETag"]}),
        )
        assert cleared.status_code == 200, cleared.text
        assert "language" not in cleared.json()
        assert (await _draft(form_id)).settings.language is None

    async def test_a_language_off_the_list_is_refused(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        response = await client.post(
            f"{BASE}/forms",
            json=dict(copy.deepcopy(SPEC), language="nl-NL"),
            headers=_auth(token),
        )
        assert response.status_code == 422, response.text

    async def test_the_op_over_the_api_and_its_dry_run(
        self, client: AsyncClient, workspace
    ):
        token = await _token(workspace.id)
        created = await _create(client, token)
        form_id, etag = created.json()["formId"], created.headers["ETag"]
        ops = {"ops": [{"op": "set_form_language", "language": "fi"}]}

        preview = await client.post(
            f"{BASE}/forms/{form_id}/ops/dry-run", json=ops, headers=_auth(token)
        )
        assert preview.status_code == 200, preview.text
        assert {"path": "/language", "before": None, "after": "fi"} in preview.json()[
            "diff"
        ]["form"]
        assert (await _draft(form_id)).settings.language is None

        applied = await client.post(
            f"{BASE}/forms/{form_id}/ops",
            json=ops,
            headers=_auth(token, **{"If-Match": etag}),
        )
        assert applied.status_code == 200, applied.text
        assert applied.json()["form"]["language"] == "fi"
        assert (await _draft(form_id)).settings.language == "fi"
