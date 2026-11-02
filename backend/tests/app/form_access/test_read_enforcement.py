"""Form-level access on the READ side: lists, search, counts, one form's
responses, a response, analytics and the mail that carries answers.

One workspace holds two published forms: an open one and one restricted to a
person with a grant. Around them: the owner, an Admin, an Editor, a Viewer, a
Privacy officer, and a Viewer who holds a grant on the restricted form. With
``FORM_ACCESS_ENABLED`` on, a member the restricted form is closed to gets the
404 of a form that is not there (never a 403), and the form is absent from
every list, count and search; Owners and Admins always see it; a granted member
sees it. With the switch off nothing changes and no new table is read.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from common.models.standard_form import StandardForm, StandardFormResponse
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import ROLE_REVIEWER, ROLE_VIEWER
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import formData, formResponse, testUser, testUser2
from tests.app.form_access.helpers import add_member, grant, restrict, set_mode
from tests.app.form_access.test_switch_and_memo import statements, touching_new_tables

OPEN_TITLE = "Open survey"
CLOSED_TITLE = "Closed survey"
SECRET = "a secret kept in the closed form"


def _cookies(user) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


async def _published(workspace, title):
    service = container.workspace_form_service()
    created = await service.create_form(
        workspace.id, StandardForm(**{**formData, "title": title}), testUser
    )
    await service.publish_form(workspace.id, created.form_id, testUser)
    return str(created.form_id)


async def _submit(workspace, form_id, user=testUser2):
    stored = await container.workspace_form_service().submit_response(
        workspace.id,
        form_id,
        StandardFormResponse(**formResponse),
        user,
    )
    return str(dict(stored)["response_id"])


@pytest.fixture()
async def world(workspace, monkeypatch):
    """The members, the forms and one response in each form; the switch is
    whatever the test sets (off unless it asks ``switch_on``)."""
    # the dashboard list names the importers through the auth service
    monkeypatch.setattr(
        container.form_service(),
        "fetch_user_details",
        AsyncMock(return_value={"users_info": []}),
    )
    members = SimpleNamespace(
        owner=testUser,
        admin=await add_member(workspace, "ADMIN"),
        editor=await add_member(workspace, "COLLABORATOR"),
        viewer=await add_member(workspace, "VIEWER"),
        officer=await add_member(workspace, "PRIVACY_OFFICER"),
        granted=await add_member(workspace, "VIEWER"),
        reviewer_granted=await add_member(workspace, "REVIEWER"),
    )
    open_id = await _published(workspace, OPEN_TITLE)
    closed_id = await _published(workspace, CLOSED_TITLE)
    open_response = await _submit(workspace, open_id)
    closed_response = await _submit(workspace, closed_id)
    # the switch is off while the data is set up: nothing here is enforced yet
    await restrict(workspace, closed_id)
    await grant(workspace, closed_id, members.granted.id, ROLE_VIEWER)
    await grant(workspace, closed_id, members.reviewer_granted.id, ROLE_REVIEWER)
    base = f"/api/v1/workspaces/{workspace.id}"
    return SimpleNamespace(
        workspace=workspace,
        who=members,
        open_id=open_id,
        closed_id=closed_id,
        open_response=open_response,
        closed_response=closed_response,
        base=base,
    )


def _ids(page) -> set:
    return {item["formId"] for item in page["items"]}


async def _get(client, user, url, **params):
    return await client.get(url, cookies=_cookies(user), params=params or None)


# -- lists, counts, search ---------------------------------------------------------


async def test_the_dashboard_list_leaves_out_a_closed_form_and_its_total(
    client: AsyncClient, world, switch_on
):
    for user in (world.who.editor, world.who.viewer):
        listed = (await _get(client, user, f"{world.base}/forms")).json()
        assert _ids(listed) >= {world.open_id}, user.sub
        assert world.closed_id not in _ids(listed), user.sub
        # the total counts what the member may open, not what exists
        assert listed["total"] == len(listed["items"])
    # a Privacy officer keeps the structure of a restricted form (and its deletion
    # requests), never its answers
    for user in (
        world.who.owner,
        world.who.admin,
        world.who.granted,
        world.who.reviewer_granted,
        world.who.officer,
    ):
        listed = (await _get(client, user, f"{world.base}/forms")).json()
        assert {world.open_id, world.closed_id} <= _ids(listed), user.sub


async def test_the_page_size_does_not_tell_of_a_closed_form(
    client: AsyncClient, world, switch_on
):
    """A page is filled from what the member may open: asking for one form
    per page, the closed form never takes a slot."""
    seen = set()
    for page in (1, 2, 3):
        listed = (
            await _get(client, world.who.editor, f"{world.base}/forms", size=1, page=page)
        ).json()
        seen |= _ids(listed)
        assert listed["total"] == len(
            (await _get(client, world.who.editor, f"{world.base}/forms")).json()["items"]
        )
    assert world.closed_id not in seen


async def test_the_pinned_list_leaves_out_a_closed_form(
    client: AsyncClient, world, switch_on
):
    repo = container.workspace_form_repo()
    for form_id in (world.open_id, world.closed_id):
        link = await repo.find_workspace_form(world.workspace.id, form_id)
        link.settings.pinned = True
        await repo.save(link)
    listed = (
        await _get(client, world.who.editor, f"{world.base}/forms", pinned_only="true")
    ).json()
    assert world.closed_id not in _ids(listed)


async def test_the_public_list_offers_a_closed_public_form_as_to_any_respondent(
    client: AsyncClient, world, switch_on
):
    """Restricted is about staff: a form open to respondents stays listed for a
    member it is restricted against, in the respondent's view."""
    listed = (
        await _get(client, world.who.editor, f"{world.base}/forms", published="true")
    ).json()
    assert {world.open_id, world.closed_id} <= _ids(listed)


async def test_a_private_form_is_restricted_and_not_in_the_public_list(
    client: AsyncClient, world, switch_on
):
    """A form flagged Private (hidden) with no mode chosen reads as restricted:
    not listed for a member who did not create it, listed for Owners and
    Admins (who did not see it before), and not offered to respondents."""
    await set_mode(world.workspace, world.open_id, hidden=True)
    for published in ("false", "true"):
        seen = (
            await _get(client, world.who.editor, f"{world.base}/forms", published=published)
        ).json()
        assert world.open_id not in _ids(seen), published
    admin_list = (await _get(client, world.who.admin, f"{world.base}/forms")).json()
    assert world.open_id in _ids(admin_list)
    assert (
        await _get(client, world.who.editor, f"{world.base}/forms/{world.open_id}")
    ).status_code == 404


async def test_search_never_names_a_closed_form(client: AsyncClient, world, switch_on):
    async def search(user, query, published="false"):
        response = await client.post(
            f"{world.base}/forms/search",
            cookies=_cookies(user),
            params={"query": query, "published": published},
        )
        assert response.status_code == 200, response.text
        return {f["formId"] for f in response.json()}

    assert await search(world.who.editor, "Closed") == set()
    assert await search(world.who.editor, "survey") == {world.open_id}
    assert await search(world.who.admin, "Closed") == {world.closed_id}
    assert await search(world.who.granted, "Closed") == {world.closed_id}


async def test_the_workspace_counts_include_only_what_the_member_may_open(
    client: AsyncClient, world, switch_on
):
    owner = (await _get(client, world.who.owner, f"{world.base}/stats")).json()
    editor = (await _get(client, world.who.editor, f"{world.base}/stats")).json()
    assert owner["forms"] == 2 and owner["responses"] == 2
    assert editor["forms"] == 1 and editor["responses"] == 1


async def test_all_submissions_and_responders_scope_to_the_forms_the_member_reads(
    client: AsyncClient, world, switch_on
):
    everything = (await _get(client, world.who.owner, f"{world.base}/all-submissions")).json()
    narrowed = (await _get(client, world.who.editor, f"{world.base}/all-submissions")).json()
    assert everything["total"] == 2
    assert narrowed["total"] == 1
    assert {i["formId"] for i in narrowed["items"]} == {world.open_id}
    granted = (await _get(client, world.who.granted, f"{world.base}/all-submissions")).json()
    assert granted["total"] == 2


async def test_a_privacy_officer_keeps_the_deletion_requests_of_a_restricted_form(
    client: AsyncClient, world, switch_on
):
    """The privacy programme stays answerable (no answers, only the queue)."""
    await container.form_response_service().request_for_response_deletion(
        world.workspace.id, world.closed_response, testUser2
    )
    queue = (
        await _get(
            client,
            world.who.officer,
            f"{world.base}/all-submissions",
            request_for_deletion="true",
        )
    ).json()
    assert {i["formId"] for i in queue["items"]} == {world.closed_id}
    # the same member reads no answers (the role never had them)
    assert (
        await _get(client, world.who.officer, f"{world.base}/all-submissions")
    ).status_code == 403


# -- one form ------------------------------------------------------------------


async def test_a_closed_form_is_a_404_for_staff_and_the_same_as_an_unknown_one(
    client: AsyncClient, world, switch_on
):
    unknown = await _get(client, world.who.editor, f"{world.base}/forms/{'0' * 24}")
    closed = await _get(client, world.who.editor, f"{world.base}/forms/{world.closed_id}")
    assert unknown.status_code == closed.status_code == 404
    assert unknown.json() == closed.json()
    for user in (world.who.owner, world.who.admin, world.who.granted):
        opened = await _get(client, user, f"{world.base}/forms/{world.closed_id}")
        assert opened.status_code == 200, (user.sub, opened.text)


async def test_the_published_read_of_a_closed_form_is_the_respondents(
    client: AsyncClient, world, switch_on
):
    staff = await _get(
        client, world.who.admin, f"{world.base}/forms/{world.closed_id}", published="true"
    )
    member = await _get(
        client, world.who.editor, f"{world.base}/forms/{world.closed_id}", published="true"
    )
    assert staff.status_code == member.status_code == 200
    # staff get the responder groups attached to the form; the respondent's
    # read of the same form carries none
    assert staff.json()["groups"] == []
    assert member.json().get("groups") is None


FORM_ROUTES = (
    "forms/{closed}/submissions",
    "forms/{closed}/all-submissions",
    "forms/{closed}/submission-paths",
    "forms/{closed}/flow-analytics",
)


@pytest.mark.parametrize("route", FORM_ROUTES)
async def test_the_responses_of_a_closed_form_are_a_404_not_a_403(
    client: AsyncClient, world, switch_on, route
):
    url = f"{world.base}/{route.format(closed=world.closed_id)}"
    unknown = f"{world.base}/{route.format(closed='0' * 24)}"
    for user in (world.who.editor, world.who.viewer):
        closed = await _get(client, user, url)
        missing = await _get(client, user, unknown)
        # exactly what a form that is not there answers (a role that lacks the
        # permission is refused alike, for every form)
        assert closed.status_code == missing.status_code, (route, user.sub)
        assert closed.json() == missing.json(), route
    editor = await _get(client, world.who.editor, url)
    assert editor.status_code == 404, (route, editor.status_code)
    for user in (world.who.owner, world.who.admin):
        assert (await _get(client, user, url)).status_code == 200, (route, user.sub)


async def test_a_grant_opens_exactly_what_its_role_gives(
    client: AsyncClient, world, switch_on
):
    submissions = f"{world.base}/forms/{world.closed_id}/submissions"
    export = f"{world.base}/forms/{world.closed_id}/all-submissions"
    # a Viewer grant reads the responses; the bulk read is an export: not for it
    assert (await _get(client, world.who.granted, submissions)).status_code == 200
    assert (await _get(client, world.who.granted, export)).status_code == 403
    assert (await _get(client, world.who.reviewer_granted, submissions)).status_code == 200


async def test_the_keyset_page_of_a_closed_form_is_a_404(
    client: AsyncClient, world, switch_on
):
    url = f"{world.base}/forms/{world.closed_id}/submissions"
    assert (await _get(client, world.who.editor, url, paging="keyset")).status_code == 404
    assert (await _get(client, world.who.granted, url, paging="keyset")).status_code == 200


# -- one response --------------------------------------------------------------


async def test_a_response_of_a_closed_form_is_a_404_for_staff_the_role_would_admit(
    client: AsyncClient, world, switch_on
):
    path = f"{world.base}/submissions/{world.closed_response}"
    missing = await _get(client, world.who.editor, f"{world.base}/submissions/{'0' * 24}")
    for user in (world.who.editor, world.who.viewer):
        closed = await _get(client, user, path)
        assert closed.status_code == 404, (user.sub, closed.status_code)
        assert closed.json() == missing.json()
    for user in (world.who.owner, world.who.admin, world.who.granted):
        assert (await _get(client, user, path)).status_code == 200, user.sub
    # and the open form's response is read as before
    assert (
        await _get(client, world.who.editor, f"{world.base}/submissions/{world.open_response}")
    ).status_code == 200


async def test_a_member_still_reads_their_own_submission_of_a_closed_form(
    client: AsyncClient, world, switch_on
):
    """Restricted is about staff: the person who answered is a respondent."""
    mine = await _submit(world.workspace, world.closed_id, user=world.who.editor)
    response = await _get(client, world.who.editor, f"{world.base}/submissions/{mine}")
    assert response.status_code == 200, response.text
    # as a respondent, not as staff: no internal fields, no staff feedback block
    assert response.json().get("internalFields") in (None, [])
    assert response.json().get("feedback") in (None,)


async def test_the_pdf_of_a_closed_form_is_a_404(client: AsyncClient, world, switch_on):
    path = f"{world.base}/submissions/{world.closed_response}/pdf"
    assert (await _get(client, world.who.editor, path)).status_code == 404
    assert (await _get(client, world.who.admin, path)).status_code != 404


async def test_staff_cannot_annotate_or_delete_through_a_closed_form(
    client: AsyncClient, world, switch_on
):
    """Each answers exactly as it does for a form that is not there."""
    cookies = _cookies(world.who.editor)
    gone = "0" * 24

    async def attempts(form_id, response_id):
        form = f"{world.base}/forms/{form_id}"
        return [
            await client.patch(
                f"{form}/submissions/{response_id}/internal-answers",
                cookies=cookies,
                json={"answers": {"x": None}},
            ),
            await client.post(
                f"{form}/submissions/{response_id}/feedback",
                cookies=cookies,
                json={"message": "hello"},
            ),
            await client.delete(f"{form}/response/{response_id}", cookies=cookies),
            await client.delete(
                f"{world.base}/submissions/{response_id}", cookies=cookies
            ),
        ]

    closed = await attempts(world.closed_id, world.closed_response)
    missing = await attempts(gone, gone)
    for refused, absent in zip(closed, missing):
        assert refused.status_code == absent.status_code, refused.request.url
        assert refused.json() == absent.json(), refused.request.url
        assert refused.status_code in (403, 404)
    # the ones the Editor's role admits are the plain 404
    assert [r.status_code for r in closed[:2]] == [404, 404]
    assert closed[3].status_code == 404


# -- analytics -----------------------------------------------------------------


@pytest.fixture()
def umami(monkeypatch):
    client = container.umami_client()
    monkeypatch.setattr(client, "fetch_stats", AsyncMock(return_value={"pageviews": 3}))
    monkeypatch.setattr(
        client,
        "fetch_pageviews",
        AsyncMock(return_value={"pageviews": [], "sessions": []}),
    )
    monkeypatch.setattr(client, "fetch_form_metrics", AsyncMock(return_value=[]))
    return client


async def _slug(world, form_id) -> str:
    link = await container.workspace_form_repo().find_workspace_form(
        world.workspace.id, form_id
    )
    return link.settings.custom_url or form_id


async def test_analytics_resolve_the_slug_to_a_form_and_refuse_a_closed_one(
    client: AsyncClient, world, switch_on, umami
):
    name = world.workspace.workspace_name
    closed_slug = await _slug(world, world.closed_id)
    open_slug = await _slug(world, world.open_id)
    window = {"start_at": 1, "end_at": 2}
    for route in ("stats", "pageviews", "metrics"):
        extra = {"pageviews": {"unit": "day", "timezone": "UTC"}, "metrics": {"type": "url"}}.get(route, {})
        closed = await client.get(
            f"/api/v1/{name}/forms/{closed_slug}/{route}",
            cookies=_cookies(world.who.editor),
            params={**window, **extra},
        )
        assert closed.status_code == 404, (route, closed.text)
        missing = await client.get(
            f"/api/v1/{name}/forms/no-such-form/{route}",
            cookies=_cookies(world.who.editor),
            params={**window, **extra},
        )
        assert missing.status_code == 404 and missing.json() == closed.json()
        for user in (world.who.admin, world.who.granted):
            ok = await client.get(
                f"/api/v1/{name}/forms/{closed_slug}/{route}",
                cookies=_cookies(user),
                params={**window, **extra},
            )
            assert ok.status_code == 200, (route, user.sub, ok.text)
        open_ok = await client.get(
            f"/api/v1/{name}/forms/{open_slug}/{route}",
            cookies=_cookies(world.who.editor),
            params={**window, **extra},
        )
        assert open_ok.status_code == 200, (route, open_ok.text)


async def test_analytics_off_ask_no_form_and_answer_as_before(
    client: AsyncClient, world, switch_off, umami
):
    """Off, the slug is not resolved at all (no extra query) and an Editor reads
    the stats of any slug, as before."""
    name = world.workspace.workspace_name
    for slug in (await _slug(world, world.closed_id), "no-such-form"):
        with statements() as seen:
            response = await client.get(
                f"/api/v1/{name}/forms/{slug}/stats",
                cookies=_cookies(world.who.editor),
                params={"start_at": 1, "end_at": 2},
            )
        assert response.status_code == 200, response.text
        assert not touching_new_tables(seen)


# -- mail is no way around it ---------------------------------------------------


async def test_a_member_who_may_not_read_a_form_is_no_recipient_of_its_answers(
    world, switch_on, monkeypatch
):
    emails = {
        str(u.id): f"{name}@acme.example"
        for name, u in vars(world.who).items()
    }

    async def users(url, params=None, **kwargs):
        return {
            "users_info": [
                {"_id": i, "email": emails[i]} for i in params["user_ids"] if i in emails
            ]
        }

    copy = container.copy_recipient_service()
    monkeypatch.setattr(copy._http_client, "get", AsyncMock(side_effect=users))
    wanted = [f"{name}@acme.example" for name in ("owner", "admin", "editor", "granted", "officer")]
    on_closed = await copy.allowed_among(wanted, world.workspace.id, world.closed_id)
    # the closed form: owner and admin by role, granted by grant; the editor,
    # whose role would admit them to an open form, and the Privacy officer, who
    # never reads answers, are no recipients
    assert on_closed == ["owner@acme.example", "admin@acme.example", "granted@acme.example"]
    on_open = await copy.allowed_among(wanted, world.workspace.id, world.open_id)
    assert on_open == [
        "owner@acme.example",
        "admin@acme.example",
        "editor@acme.example",
        "granted@acme.example",
    ]
    # "send me a copy": the same rule on a single address
    assert not await copy.is_allowed("editor@acme.example", world.workspace.id, world.closed_id)
    assert await copy.is_allowed("editor@acme.example", world.workspace.id, world.open_id)


async def test_the_recipient_rule_is_off_while_the_switch_is_off(
    world, switch_off, monkeypatch
):
    emails = {str(world.who.editor.id): "editor@acme.example"}

    async def users(url, params=None, **kwargs):
        return {
            "users_info": [
                {"_id": i, "email": emails[i]} for i in params["user_ids"] if i in emails
            ]
        }

    copy = container.copy_recipient_service()
    monkeypatch.setattr(copy._http_client, "get", AsyncMock(side_effect=users))
    assert await copy.is_allowed("editor@acme.example", world.workspace.id, world.closed_id)


# -- the key surfaces' lists ----------------------------------------------------


def _key(world, user):
    return SimpleNamespace(
        workspace_id=world.workspace.id, created_by=str(user.id), name="reader", id="k"
    )


async def test_the_mcp_tools_see_only_the_forms_the_keys_creator_may_open(
    world, switch_on
):
    from backend.app.mcp.server import _workspace_form_ids

    editor_sees = await _workspace_form_ids(_key(world, world.who.editor))
    assert set(editor_sees) == {world.open_id}
    admin_sees = await _workspace_form_ids(_key(world, world.who.admin))
    assert set(admin_sees) == {world.open_id, world.closed_id}
    privacy = await _workspace_form_ids(
        _key(world, world.who.officer), Permission.PRIVACY_MANAGE
    )
    assert world.closed_id in privacy


async def test_the_public_list_narrows_before_it_counts(world, switch_on):
    from backend.app.public_api import routes
    from backend.app.public_api.auth import ApiCaller
    from backend.app.services.api_access import acting_user

    editor_key = _key(world, world.who.editor)
    listed = await routes.list_forms(
        page=1, size=50, caller=ApiCaller(key=editor_key, user=acting_user(editor_key))
    )
    body = json.loads(listed.body)
    assert {i["formId"] for i in body["items"]} == {world.open_id}
    assert body["total"] == 1
    admin_key = _key(world, world.who.admin)
    everything = json.loads(
        (
            await routes.list_forms(
                page=1, size=50, caller=ApiCaller(key=admin_key, user=acting_user(admin_key))
            )
        ).body
    )
    assert everything["total"] == 2


# -- switch off: nothing changes -------------------------------------------------


async def test_off_every_member_reads_as_before_and_no_new_table_is_touched(
    client: AsyncClient, world, switch_off
):
    assert world.workspace  # stored grants and a restricted mode exist
    calls = (
        (world.who.editor, f"{world.base}/forms", {}),
        (world.who.editor, f"{world.base}/forms", {"published": "true"}),
        (world.who.editor, f"{world.base}/forms/{world.closed_id}", {}),
        (world.who.editor, f"{world.base}/stats", {}),
        (world.who.editor, f"{world.base}/all-submissions", {}),
        (world.who.editor, f"{world.base}/forms/{world.closed_id}/submissions", {}),
        (world.who.editor, f"{world.base}/forms/{world.closed_id}/submission-paths", {}),
        (world.who.editor, f"{world.base}/submissions/{world.closed_response}", {}),
    )
    with statements() as seen:
        for user, url, params in calls:
            response = await _get(client, user, url, **params)
            assert response.status_code == 200, (url, response.text)
    assert not touching_new_tables(seen)
    # the Editor reads the form the access mode would close, exactly as before
    listed = (await _get(client, world.who.editor, f"{world.base}/forms")).json()
    assert {world.open_id, world.closed_id} <= _ids(listed)
    assert (await _get(client, world.who.editor, f"{world.base}/stats")).json()["forms"] == 2


# Statements per request with the switch off, measured on the commit before the
# read side was enforced, for a request after a first one (an Admin and an
# Editor alike). A change that adds a query on these paths while the switch is
# off has to raise a number here knowingly.
OFF_STATEMENTS = {
    "forms": 10,
    "forms?published=true": 9,
    "forms/{open}": 10,
    "forms/{open}/submissions": 8,
    "forms/{open}/submissions?paging=keyset": 8,
    "submissions/{response}": 7,
    "all-submissions": 7,
    "stats": 9,
    "forms/{open}/submission-paths": 6,
}


async def test_off_the_main_reads_run_no_more_statements_than_before(
    client: AsyncClient, world, switch_off
):
    for route, limit in OFF_STATEMENTS.items():
        url = f"{world.base}/" + route.format(
            open=world.open_id, response=world.open_response
        )
        for user in (world.who.admin, world.who.editor):
            await client.get(url, cookies=_cookies(user))  # warm what is cached
            with statements() as seen:
                response = await client.get(url, cookies=_cookies(user))
            assert response.status_code == 200, (route, response.text)
            assert len(seen) <= limit, (route, user.sub, len(seen), limit)
