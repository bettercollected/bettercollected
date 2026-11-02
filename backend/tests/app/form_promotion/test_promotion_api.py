"""Copying a form to another workspace: preview and apply, with the switch on.

Two workspaces: A (``testUser`` owns it) and B (``testUser1`` owns it, ``testUser``
is added to it with the role a test needs).
"""

import json

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_audit_event import FORM_COPIED_OUT, FORM_PROMOTED
from backend.app.services.form_access.model import MODE_RESTRICTED
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.helpers import audit_events, cookies, fail_audit
from tests.app.form_promotion.helpers import (
    FOREIGN_IMAGE,
    UNSPLASH,
    add_automations,
    body,
    create_source,
    headers,
    make_member,
    on,
    option_list,
    spec_document,
    stored_spec,
    url,
)

pytestmark = pytest.mark.asyncio

ADMIN = WorkspaceRoles.ADMIN.value
EDITOR = WorkspaceRoles.COLLABORATOR.value
VIEWER = WorkspaceRoles.VIEWER.value


@pytest.fixture(autouse=True)
def switched_on(monkeypatch):
    on(monkeypatch)


@pytest.fixture()
async def world(workspace, workspace_1):
    """A source form in A; the caller (testUser, Owner of A) is an Admin of B."""
    await make_member(workspace_1, testUser, ADMIN)
    form_id, etag = await create_source(workspace)
    return type(
        "World",
        (),
        {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag},
    )


async def preview(client, w, user=testUser, form_id=None, **more):
    return await client.post(
        url(w.a, form_id or w.form_id, "/promotion/preview"),
        json=body(w.b, **more),
        cookies=cookies(user),
    )


async def apply(client, w, user=testUser, form_id=None, key=None, **more):
    payload = body(w.b, sourceEtag=w.etag, **more)
    return await client.post(
        url(w.a, form_id or w.form_id, "/promotion/apply"),
        json=payload,
        cookies=cookies(user),
        headers=headers(key),
    )


async def forms_of(workspace):
    return {str(link.form_id) for link in await container.workspace_form_repo().list_in_workspace(workspace.id)}


# -- preview --------------------------------------------------------------------------
async def test_a_preview_stores_nothing_and_says_what_would_happen(client, world):
    before = await forms_of(world.b)
    await add_automations(world.a, world.form_id, webhooks=2, emails=1, registrations=1)
    response = await preview(client, world)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["valid"] is True and data["errors"] == []
    assert data["created"] is True and data["diff"] is None
    assert data["counts"] == {"pages": 1, "questions": 2}
    assert data["sourceEtag"] == world.etag and data["targetEtag"] is None
    assert data["notCarried"] == {
        "webhooks": 2,
        "emailActions": 1,
        "sheets": 0,
        "registrations": 1,
    }
    assert "responses" in data["alsoNotCopied"]
    assert data["copyIsRestricted"] is False
    assert await forms_of(world.b) == before
    # a preview writes no audit entry: nothing was copied
    assert await audit_events(world.a, FORM_COPIED_OUT) == []


async def test_the_report_names_counts_never_an_address_a_secret_or_a_recipient(
    client, world
):
    await add_automations(world.a, world.form_id, webhooks=1, emails=1, registrations=1)
    response = await preview(client, world)
    text = response.text
    for forbidden in (
        "voorbeeld.example",
        "SEALED",
        "ontvanger@",
        "zaken/voorbeeld",
        "Mail 0",
    ):
        assert forbidden not in text


async def test_what_is_adjusted_is_counted_and_the_form_still_copies(
    client, workspace, workspace_1, monkeypatch
):
    """Images of another instance are not first-party here: the rule drops them
    and the copy goes on without them."""
    from backend.app.services.form_promotion.service import FormPromotionService

    await make_member(workspace_1, testUser, ADMIN)
    source = spec_document()
    source["pages"][0]["fields"][1]["imageUrl"] = UNSPLASH
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, source, testUser
    )
    world = type(
        "W", (), {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag}
    )
    monkeypatch.setattr(FormPromotionService, "_image_rule", staticmethod(lambda u: None))
    seen = await preview(client, world)
    assert seen.json()["valid"] is True
    assert seen.json()["adjusted"]["counts"] == {"imagesDropped": 1}
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    assert response.json()["adjusted"] == {"imagesDropped": 1}
    spec, _ = await stored_spec(workspace_1, response.json()["formId"])
    assert "imageUrl" not in spec["pages"][0]["fields"][1]
    (came,) = await audit_events(workspace_1, FORM_PROMOTED)
    assert came.count == 1


@pytest.fixture()
def lists_on(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)


async def test_option_lists_are_matched_by_name_in_the_target(
    client, workspace, workspace_1, lists_on
):
    await make_member(workspace_1, testUser, ADMIN)
    on_a = await option_list(workspace, "Gemeenten", "Een", "Twee")
    on_b = await option_list(workspace_1, "Gemeenten", "Uno", "Dos")
    source = spec_document()
    source["pages"][0]["fields"] = [
        {
            "id": q,
            "type": "dropdown",
            "title": q,
            "optionSource": {"kind": "list", "listId": str(on_a.id)},
        }
        for q in ("stad", "dorp")
    ]
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, source, testUser
    )
    world = type(
        "W", (), {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag}
    )
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    spec, _ = await stored_spec(workspace_1, response.json()["formId"])
    listed = {q["id"]: q["optionSource"]["listId"] for q in spec["pages"][0]["fields"]}
    assert listed == {"stad": str(on_b.id), "dorp": str(on_b.id)}
    assert str(on_a.id) not in json.dumps(spec)
    assert response.json()["adjusted"]["listsMatchedByName"] == 2
    # the list itself never moved: the target's items are its own
    assert [i.label for i in (await container.option_list_repo().get(workspace_1.id, on_b.id)).items] == ["Uno", "Dos"]


async def test_a_list_the_target_does_not_have_is_dropped_and_reported(
    client, workspace, workspace_1, lists_on
):
    await make_member(workspace_1, testUser, ADMIN)
    only_here = await option_list(workspace, "Alleen hier", "X")
    source = spec_document()
    source["pages"][0]["fields"] = [
        {
            "id": "stad",
            "type": "dropdown",
            "title": "Stad",
            "optionSource": {"kind": "list", "listId": str(only_here.id)},
        }
    ]
    form_id, _, etag = await container.form_spec_writer().create(
        workspace.id, source, testUser
    )
    world = type("W", (), {"a": workspace, "b": workspace_1, "form_id": form_id, "etag": etag})
    seen = (await preview(client, world)).json()
    assert seen["valid"] is True
    assert seen["adjusted"]["listsNotFound"] == ["stad"]
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    spec, _ = await stored_spec(workspace_1, response.json()["formId"])
    assert "optionSource" not in spec["pages"][0]["fields"][0]


# -- apply: a new form ------------------------------------------------------------------
async def test_apply_makes_a_new_draft_with_the_document_and_marks_where_it_came_from(
    client, world
):
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["created"] is True and data["workspaceId"] == str(world.b.id)
    assert data["etag"] and response.headers["etag"] == data["etag"]
    new_id = data["formId"]
    assert new_id != world.form_id
    # the same document, and a draft: nothing published
    spec_a, _ = await stored_spec(world.a, world.form_id)
    spec_b, etag = await stored_spec(world.b, new_id)
    assert spec_b == spec_a
    assert etag == data["etag"]
    assert await container.form_repo().get_latest_version_of_form(new_id) is None
    # (a new form takes the data protection settings)
    assert spec_b["trust"]["retention"] == {"type": "days", "value": 90}
    link = await container.workspace_form_repo().find_workspace_form(world.b.id, new_id)
    mark = link.settings.promoted_from
    assert (mark.workspace_id, mark.form_id) == (str(world.a.id), world.form_id)
    assert mark.by == testUser.id and mark.source_hash
    # the source is untouched
    assert (await stored_spec(world.a, world.form_id))[1] == world.etag


async def test_the_copy_is_never_published_even_from_a_published_source(client, world):
    await container.workspace_form_service().publish_form(
        world.a.id, world.form_id, testUser
    )
    # (publishing does not change what the draft says)
    spec, etag = await stored_spec(world.a, world.form_id)
    world.etag = etag
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    new_id = response.json()["formId"]
    assert await container.form_repo().get_latest_version_of_form(new_id) is None
    link = await container.workspace_form_repo().find_workspace_form(world.b.id, new_id)
    assert not getattr(link.settings, "is_published", None)


async def test_what_never_moves_does_not_exist_in_the_copy(client, world):
    await add_automations(world.a, world.form_id, webhooks=1, emails=1, registrations=1)
    response = await apply(client, world)
    new_id = response.json()["formId"]
    assert response.json()["notCarried"] == {
        "webhooks": 1,
        "emailActions": 1,
        "sheets": 0,
        "registrations": 1,
    }
    repo = container
    assert await repo.form_webhook_repo().count_for_form(world.b.id, new_id) == 0
    assert await repo.form_email_action_repo().count_for_form(world.b.id, new_id) == 0
    assert await repo.form_registration_repo().count_for_form(world.b.id, new_id) == 0
    # the mark keeps the counts, never an address
    link = await repo.workspace_form_repo().find_workspace_form(world.b.id, new_id)
    assert link.settings.promoted_from.not_carried["webhooks"] == 1
    assert "voorbeeld" not in json.dumps(link.settings.promoted_from.model_dump(mode="json"))


# -- apply: an existing target ---------------------------------------------------------------
async def _existing_target(world, **changes):
    form_id, _, _ = await container.form_spec_writer().create(
        world.b.id, spec_document(**{"title": "Oud", **changes}), testUser
    )
    spec, etag = await stored_spec(world.b, form_id)
    return form_id, etag


async def test_an_existing_target_keeps_its_data_protection_settings_unless_ticked(
    client, world
):
    target, target_etag = await _existing_target(
        world,
        trust={
            "purpose": "Eigen doel",
            "retention": {"type": "days", "value": 365},
            "privacyPolicyUrl": "https://privacy.voorbeeld.example/doel",
            "requireVerifiedIdentity": False,
        },
    )
    response = await apply(
        client, world, targetFormId=target, targetEtag=target_etag
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] is False and response.json()["formId"] == target
    spec, _ = await stored_spec(world.b, target)
    # the content came across ...
    assert spec["title"] == "Aanmelding"
    # ... the data protection settings stayed
    assert spec["trust"]["purpose"] == "Eigen doel"
    assert spec["trust"]["retention"] == {"type": "days", "value": 365}
    assert spec["trust"]["privacyPolicyUrl"].endswith("/doel")
    assert spec["trust"]["requireVerifiedIdentity"] is False
    # (the four of them the source document sets)
    assert response.json()["adjusted"]["dataProtectionKept"] == 4


async def test_ticking_copies_the_data_protection_settings(client, world):
    target, target_etag = await _existing_target(
        world,
        trust={
            "purpose": "Eigen doel",
            "retention": {"type": "days", "value": 30},
        },
    )
    # (90 days replaces 30: longer, no confirmation)
    response = await apply(
        client,
        world,
        targetFormId=target,
        targetEtag=target_etag,
        copyDataProtection=True,
    )
    assert response.status_code == 200, response.text
    spec, _ = await stored_spec(world.b, target)
    assert spec["trust"]["purpose"] == "Aanmelden"
    assert spec["trust"]["retention"] == {"type": "days", "value": 90}


async def test_shortening_a_retention_needs_a_second_confirmation(client, world):
    target, target_etag = await _existing_target(
        world,
        trust={"retention": {"type": "days", "value": 400}},
    )
    more = dict(targetFormId=target, targetEtag=target_etag, copyDataProtection=True)
    asked = await preview(client, world, **more)
    assert asked.json()["retentionShortened"] is True
    refused = await apply(client, world, **more)
    assert refused.status_code == 422
    assert refused.json()["code"] == "retention_confirmation_required"
    assert (await stored_spec(world.b, target))[0]["trust"]["retention"]["value"] == 400
    done = await apply(client, world, confirmShorterRetention=True, **more)
    assert done.status_code == 200, done.text
    assert (await stored_spec(world.b, target))[0]["trust"]["retention"]["value"] == 90


async def test_updating_a_published_target_changes_the_draft_only(client, world):
    target, _ = await _existing_target(world)
    await container.workspace_form_service().publish_form(
        world.b.id, target, testUser
    )
    version_before = await container.form_repo().get_latest_version_of_form(target)
    _, target_etag = await stored_spec(world.b, target)
    response = await apply(
        client, world, targetFormId=target, targetEtag=target_etag
    )
    assert response.status_code == 200, response.text
    after = await container.form_repo().get_latest_version_of_form(target)
    assert after.title == version_before.title == "Oud"
    assert (await stored_spec(world.b, target))[0]["title"] == "Aanmelding"


async def test_the_preview_of_an_existing_target_has_the_diff_and_its_etag(client, world):
    target, target_etag = await _existing_target(world)
    response = await preview(client, world, targetFormId=target)
    data = response.json()
    assert data["created"] is False and data["targetEtag"] == target_etag
    assert data["diff"]["changed"] is True
    assert any(entry["kind"] for entry in data["diff"]["entries"])


async def test_a_target_changed_since_the_last_copy_needs_overwrite(client, world):
    first = await apply(client, world)
    target = first.json()["formId"]
    spec, etag = await stored_spec(world.b, target)
    # someone edits the copy here
    spec["title"] = "Hier aangepast"
    await container.form_spec_writer().replace(world.b.id, target, spec, [etag], testUser)
    _, etag = await stored_spec(world.b, target)
    refused = await apply(client, world, targetFormId=target, targetEtag=etag)
    assert refused.status_code == 409
    assert refused.json()["code"] == "target_changed"
    seen = await preview(client, world, targetFormId=target)
    assert seen.json()["targetChangedSinceLastPromotion"] is True
    done = await apply(
        client, world, targetFormId=target, targetEtag=etag, overwrite=True
    )
    assert done.status_code == 200, done.text
    assert (await stored_spec(world.b, target))[0]["title"] == "Aanmelding"
    # an untouched copy is no change
    again = await preview(client, world, targetFormId=target)
    assert again.json()["targetChangedSinceLastPromotion"] is False


async def test_a_form_cannot_be_copied_onto_itself(client, world):
    response = await client.post(
        url(world.a, world.form_id, "/promotion/preview"),
        json={"targetWorkspaceId": str(world.a.id), "targetFormId": world.form_id},
        cookies=cookies(testUser),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "same_form"


# -- ETags and idempotency -----------------------------------------------------------------
async def test_a_stale_source_etag_is_412_and_nothing_is_written(client, world):
    before = await forms_of(world.b)
    world.etag = '"stale"'
    response = await apply(client, world)
    assert response.status_code == 412, response.text
    assert await forms_of(world.b) == before
    assert await audit_events(world.b, FORM_PROMOTED) == []


async def test_a_stale_target_etag_is_412(client, world):
    target, target_etag = await _existing_target(world)
    response = await apply(
        client, world, targetFormId=target, targetEtag='"stale"'
    )
    assert response.status_code == 412, response.text
    assert (await stored_spec(world.b, target))[0]["title"] == "Oud"
    # the preview refuses a stale ETag too
    seen = await preview(client, world, targetFormId=target, targetEtag='"stale"')
    assert seen.status_code == 412


async def test_a_source_changed_after_the_preview_is_412(client, world):
    seen = await preview(client, world)
    spec, etag = await stored_spec(world.a, world.form_id)
    spec["title"] = "Veranderd"
    await container.form_spec_writer().replace(
        world.a.id, world.form_id, spec, [etag], testUser
    )
    world.etag = seen.json()["sourceEtag"]
    response = await apply(client, world)
    assert response.status_code == 412


async def test_an_update_needs_the_target_etag_and_a_new_form_sends_none(client, world):
    target, target_etag = await _existing_target(world)
    missing = await apply(client, world, targetFormId=target)
    assert missing.status_code == 422
    extra = await apply(client, world, targetEtag=target_etag)
    assert extra.status_code == 422


async def test_the_same_key_replays_and_makes_no_second_form(client, world):
    before = await forms_of(world.b)
    first = await apply(client, world, key="sleutel-1")
    second = await apply(client, world, key="sleutel-1")
    assert (first.status_code, second.status_code) == (201, 201)
    assert second.json()["formId"] == first.json()["formId"]
    assert second.headers["idempotent-replayed"] == "true"
    assert len(await forms_of(world.b) - before) == 1
    assert len(await audit_events(world.b, FORM_PROMOTED)) == 1


async def test_the_same_key_with_another_request_is_refused(client, world):
    await apply(client, world, key="sleutel-2")
    other = await apply(client, world, key="sleutel-2", copyDataProtection=True)
    assert other.status_code == 422
    assert other.json()["code"] == "idempotency_key_reused"


async def test_an_idempotency_key_is_required(client, world):
    response = await client.post(
        url(world.a, world.form_id, "/promotion/apply"),
        json=body(world.b, sourceEtag=world.etag),
        cookies=cookies(testUser),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_required"


async def test_a_412_is_not_kept_for_the_key(client, world):
    good = world.etag
    world.etag = '"stale"'
    assert (await apply(client, world, key="sleutel-3")).status_code == 412
    world.etag = good
    assert (await apply(client, world, key="sleutel-3")).status_code == 201


# -- the audit -----------------------------------------------------------------------------
async def test_both_sides_are_audited_with_ids_and_counts_only(client, world):
    response = await apply(client, world)
    new_id = response.json()["formId"]
    (out,) = await audit_events(world.a, FORM_COPIED_OUT)
    (came,) = await audit_events(world.b, FORM_PROMOTED)
    assert out.user_id == came.user_id == testUser.id
    assert out.form_id == world.form_id
    assert out.target_workspace_id == str(world.b.id)
    assert came.form_id == new_id
    assert (came.source_workspace_id, came.source_form_id) == (
        str(world.a.id),
        world.form_id,
    )
    assert came.count == 0
    dumped = json.dumps([out.model_dump(mode="json"), came.model_dump(mode="json")])
    assert "Aanmelding" not in dumped


async def test_an_audit_store_that_is_down_refuses_the_copy_and_writes_nothing(
    client, world, monkeypatch
):
    before = await forms_of(world.b)
    fail_audit(monkeypatch)
    response = await apply(client, world)
    assert response.status_code == 503
    assert response.json()["code"] == "audit_unavailable"
    assert await forms_of(world.b) == before


async def test_the_two_kinds_show_in_the_activity_reader(client, world, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "AUDIT_LOG_UI_ENABLED", True)
    await apply(client, world)
    async def feed(workspace):
        page = await client.get(
            f"/api/v1/workspaces/{workspace.id}/audit-log",
            params={"area": "forms"},
            cookies=cookies(testUser),
        )
        assert page.status_code == 200, page.text
        return page.json()["entries"]

    out = await feed(world.a)
    assert [e["event"] for e in out] == [FORM_COPIED_OUT]
    assert out[0]["area"] == "forms"
    came = await feed(world.b)
    assert [e["event"] for e in came] == [FORM_PROMOTED]
    # the other workspace's id is not part of the reader's entry
    assert str(world.a.id) not in json.dumps(came)
    assert str(world.b.id) not in json.dumps(out)


# -- the restricted form ----------------------------------------------------------------------
async def test_a_restricted_source_gives_a_restricted_copy_in_one_write(
    client, world, monkeypatch
):
    from backend.config import settings

    await container.workspace_form_repo().set_access_mode(
        world.a.id, world.form_id, MODE_RESTRICTED
    )
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    seen = await preview(client, world)
    assert seen.json()["copyIsRestricted"] is True
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    link = await container.workspace_form_repo().find_workspace_form(
        world.b.id, response.json()["formId"]
    )
    assert link.settings.access_mode == MODE_RESTRICTED
    # no grant came along
    grants = await container.form_access_grant_repo().list_for_form(
        world.b.id, response.json()["formId"]
    )
    assert [g for g in grants if g.subject_type != "user"] == []


async def test_a_restricted_copy_is_restricted_with_the_switch_off_too(client, world):
    await container.workspace_form_repo().set_access_mode(
        world.a.id, world.form_id, MODE_RESTRICTED
    )
    response = await apply(client, world)
    link = await container.workspace_form_repo().find_workspace_form(
        world.b.id, response.json()["formId"]
    )
    assert link.settings.access_mode == MODE_RESTRICTED


# -- the spec file ---------------------------------------------------------------------------
async def test_the_form_file_is_the_document_and_is_audited_and_never_cached(
    client, world
):
    response = await client.get(
        url(world.a, world.form_id, "/spec-file"), cookies=cookies(testUser)
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="form-{world.form_id}.json"'
    )
    assert response.json() == (await stored_spec(world.a, world.form_id))[0]
    (out,) = await audit_events(world.a, FORM_COPIED_OUT)
    assert out.form_id == world.form_id and out.target_workspace_id is None


async def test_no_audit_row_no_file(client, world, monkeypatch):
    fail_audit(monkeypatch)
    response = await client.get(
        url(world.a, world.form_id, "/spec-file"), cookies=cookies(testUser)
    )
    assert response.status_code == 503
    assert "Aanmelding" not in response.text


# -- the target picker ------------------------------------------------------------------------
async def test_the_picker_lists_forms_the_caller_may_edit_copies_of_this_first(client, world):
    await _existing_target(world, title="Zzz laatste")
    copy = await apply(client, world)
    await _existing_target(world, title="Aaa eerste")
    listed = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(world.b.id)},
        cookies=cookies(testUser),
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert items[0]["formId"] == copy.json()["formId"]
    assert items[0]["copiedFromSource"] is True
    assert [i["copiedFromSource"] for i in items[1:]] == [False, False]
    assert [i["title"] for i in items[1:]] == ["Aaa eerste", "Zzz laatste"]
    narrowed = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(world.b.id), "q": "laatste"},
        cookies=cookies(testUser),
    )
    assert [i["title"] for i in narrowed.json()["items"]] == ["Zzz laatste"]


async def test_the_picker_says_nothing_of_a_workspace_the_caller_is_not_in(
    client, world, workspace_pro
):
    response = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": str(workspace_pro.id)},
        cookies=cookies(testUser1),
    )
    assert response.status_code in (403, 404)
    absent = await client.get(
        url(world.a, world.form_id, "/promotion/targets"),
        params={"targetWorkspaceId": "0" * 24},
        cookies=cookies(testUser),
    )
    assert absent.status_code == 404
    assert absent.json() == {"message": "Workspace not found"} or "Workspace" in absent.text


async def test_the_retention_question_is_not_kept_for_the_key(client, world):
    """The confirmation is a question for the person: the same key goes again with
    the answer, and the copy runs once."""
    target, target_etag = await _existing_target(
        world, trust={"retention": {"type": "days", "value": 400}}
    )
    more = dict(targetFormId=target, targetEtag=target_etag, copyDataProtection=True)
    asked = await apply(client, world, key="sleutel-4", **more)
    assert asked.status_code == 422
    done = await apply(
        client, world, key="sleutel-4", confirmShorterRetention=True, **more
    )
    assert done.status_code == 200, done.text


async def test_connected_actions_are_counted_as_sheets_and_do_not_move(client, world):
    from common.models.standard_form import ActionState

    def attach(stored):
        stored.actions = {"on_submit": [ActionState(id=RecordId()), ActionState(id=RecordId())]}

    await container.form_repo().mutate_draft(RecordId(world.form_id), attach)
    spec, world.etag = await stored_spec(world.a, world.form_id)
    response = await apply(client, world)
    assert response.status_code == 201, response.text
    assert response.json()["notCarried"]["sheets"] == 2
    copy = await container.form_repo().get_form_document_by_id(response.json()["formId"])
    assert not copy.actions
