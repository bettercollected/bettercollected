"""The options route answers only for a form a respondent may fill in right
now, as the submit gate reads it: not hidden, open, not full, a signed-in
respondent where the form asks for a verified identity, a member of a responder
group when it is private. Judged at every call; one 404 for everything else."""

import datetime as dt
import json

import pytest
from common.models.user import User
from common.records import RecordId
from httpx import AsyncClient

from backend.app.container import container
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1
from tests.app.option_sources.helpers import make_list, publish, question

pytestmark = pytest.mark.asyncio

STRANGER = User(id=str(RecordId()), sub="stranger@elsewhere.test")


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


def _cookies(user) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def url(workspace, form):
    return f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/options/city"


def _in(**delta) -> str:
    return (
        (dt.datetime.now(dt.timezone.utc) + dt.timedelta(**delta))
        .replace(microsecond=0)
        .isoformat()
    )


@pytest.fixture()
async def form(workspace):
    created = await make_list(workspace)
    return await publish(
        workspace,
        [
            question(
                "city",
                "dropdown",
                "City",
                source={"kind": "list", "list_id": created.id},
            )
        ],
        title="Cities",
    )


async def settings_of(workspace, form, **values):
    repo = container.workspace_form_repo()
    link = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form.form_id)
    )
    for key, value in values.items():
        setattr(link.settings, key, value)
    await repo.update(link.id, link)


async def plain_404(client, address, **kwargs):
    response = await client.get(address, **kwargs)
    assert response.status_code == 404, response.text
    return response


@pytest.mark.parametrize(
    "values",
    [
        {"hidden": True},
        {"form_close_date": _in(days=-1)},
        {"form_close_date": "2001-01-01T00:00:00+02:00"},
        {"form_open_date": _in(days=3)},
        {"private": True},
        {"require_verified_identity": True},
    ],
    ids=[
        "hidden",
        "closed",
        "closed-with-offset",
        "not-yet-open",
        "private",
        "verified",
    ],
)
async def test_a_form_the_public_may_not_fill_in_gives_the_same_404(
    client: AsyncClient, workspace, form, values
):
    address = url(workspace, form)
    assert (await client.get(address)).status_code == 200
    await settings_of(workspace, form, **values)
    # the structure may still be cached: the access never is
    first = await plain_404(client, address)
    second = await plain_404(client, address, params={"q": "x"})
    assert first.text == second.text
    unknown = await client.get(
        url(workspace, form).replace(str(form.form_id), str(RecordId()))
    )
    assert unknown.text == first.text


async def test_a_form_that_just_closed_or_got_hidden_is_not_served_from_the_cache(
    client: AsyncClient, workspace, form
):
    address = url(workspace, form)
    assert (await client.get(address)).status_code == 200
    await settings_of(workspace, form, hidden=True)
    await plain_404(client, address)
    await settings_of(workspace, form, hidden=False, form_close_date=_in(days=-1))
    await plain_404(client, address)
    await settings_of(workspace, form, form_close_date=None)
    assert (await client.get(address)).status_code == 200


async def test_a_full_form_gives_the_404_and_a_free_slot_serves_again(
    client: AsyncClient, workspace, form
):
    address = url(workspace, form)
    await settings_of(workspace, form, response_limit=1)
    assert (await client.get(address)).status_code == 200
    submit = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/response",
        data={"response": json.dumps({"answers": {}})},
    )
    assert submit.status_code == 200, submit.text
    await plain_404(client, address)
    await settings_of(workspace, form, response_limit=5)
    assert (await client.get(address)).status_code == 200


async def test_a_verified_identity_form_needs_a_signed_in_respondent(
    client: AsyncClient, workspace, form
):
    await settings_of(workspace, form, require_verified_identity=True)
    address = url(workspace, form)
    await plain_404(client, address)
    await plain_404(
        client, address, cookies={"Authorization": "x.y.z", "RefreshToken": "x.y.z"}
    )
    assert (await client.get(address, cookies=_cookies(STRANGER))).status_code == 200


async def _private(workspace, form, member=testUser1):
    await settings_of(workspace, form, private=True)
    groups = container.responder_groups_repository()
    group = await groups.create_group(workspace.id, "Neighbours")
    await groups.add_emails_to_group(group.id, [member.sub])
    await groups.add_groups_to_form(str(form.form_id), [group.id])


async def test_a_private_form_serves_only_the_members_of_its_groups(
    client: AsyncClient, workspace, form
):
    await _private(workspace, form)
    address = url(workspace, form)
    await plain_404(client, address)  # nobody signed in
    for user in (STRANGER, testUser):  # signed in, not in the group (the owner neither)
        await plain_404(client, address, cookies=_cookies(user))
    member = await client.get(address, cookies=_cookies(testUser1))
    assert member.status_code == 200 and member.json()["total"] == 5
    assert member.headers["cache-control"] == "no-store"


async def test_one_users_access_never_serves_another(
    client: AsyncClient, workspace, form
):
    await _private(workspace, form)
    address = url(workspace, form)
    assert (await client.get(address, cookies=_cookies(testUser1))).status_code == 200
    # right after the member was served, a stranger is still refused
    await plain_404(client, address, cookies=_cookies(STRANGER))
    assert (await client.get(address, cookies=_cookies(testUser1))).status_code == 200


async def test_a_hidden_private_form_serves_nobody(
    client: AsyncClient, workspace, form
):
    await _private(workspace, form)
    await settings_of(workspace, form, hidden=True)
    await plain_404(client, url(workspace, form), cookies=_cookies(testUser1))


async def test_the_user_is_read_only_for_a_form_that_asks_for_one(
    client: AsyncClient, workspace, form, monkeypatch
):
    from backend.app.controllers import workspace_responses

    reads = []
    real = workspace_responses.get_user_if_logged_in

    async def spy(request, response):
        reads.append(1)
        return await real(request, response)

    monkeypatch.setattr(workspace_responses, "get_user_if_logged_in", spy)
    assert (
        await client.get(url(workspace, form), cookies=_cookies(testUser1))
    ).status_code == 200
    assert reads == []
    await _private(workspace, form)
    await client.get(url(workspace, form), cookies=_cookies(testUser1))
    assert reads == [1]


async def test_a_client_is_limited_before_any_query(
    client: AsyncClient, workspace, form, monkeypatch
):
    from backend.app.services.option_sources import service as module

    monkeypatch.setattr(module, "RATE_PER_CLIENT", 1)
    monkeypatch.setattr(module, "COARSE_FACTOR", 2)
    service = container.option_source_service()
    queries = []
    original = service._workspace_forms.get_workspace_form_with_custom_slug_form_id

    async def counted(*args, **kwargs):
        queries.append(1)
        return await original(*args, **kwargs)

    monkeypatch.setattr(
        service._workspace_forms, "get_workspace_form_with_custom_slug_form_id", counted
    )
    address = url(workspace, form)
    unknown = address.replace(str(form.form_id), str(RecordId()))
    statuses = [(await client.get(unknown)).status_code for _ in range(4)]
    # two are let through to the lookup (and are 404), then the client is limited from memory
    assert statuses == [404, 404, 429, 429] and len(queries) == 2
    limited = await client.get(address)
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
