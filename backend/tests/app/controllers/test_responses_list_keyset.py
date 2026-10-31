"""The staff responses list: filters, sort and keyset paging on plaintext
columns (``GET .../forms/{form}/submissions``), its cursor and its roles."""

import datetime as dt

import pytest
from common.ids import RecordId
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.repositories.postgres import responses as responses_module
from backend.app.schemas.standard_form_response import DeletionRequestStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import response_cursor, response_paging
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1, formData
from common.models.standard_form import StandardForm

BASE = dt.datetime(2026, 3, 1, 12, 0, 0, tzinfo=dt.timezone.utc)
SECRET_ANSWER = "the-answer-never-listed-in-plaintext"


def cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


class Seed:
    """Stores responses of one form with a controlled submission time."""

    def __init__(self, workspace, form_id, monkeypatch):
        self.workspace = workspace
        self.form_id = form_id
        self.monkeypatch = monkeypatch
        self.repo = container.form_response_repo()

    async def add(
        self, minutes: int, owner=None, version=1, status=None, micro=0
    ) -> str:
        moment = BASE + dt.timedelta(minutes=minutes, microseconds=micro)
        self.monkeypatch.setattr(responses_module, "utcnow", lambda: moment)
        response = StandardFormResponse(
            response_id=str(RecordId()),
            answers={"q1": {"type": "text", "text": SECRET_ANSWER}},
            dataOwnerIdentifier=owner,
            form_version=version,
        )
        stored = await self.repo.save_form_response(
            self.form_id, response, self.workspace.id
        )
        if status is not None:
            request = await self.repo.add_deletion_request(stored, stored.response_id)
            if status != DeletionRequestStatus.PENDING:
                await self.repo.close_deletion_request(request, status, "staff-1")
        return stored.response_id


@pytest.fixture()
async def seed(workspace, published_form, monkeypatch):
    return Seed(workspace, published_form.form_id, monkeypatch)


@pytest.fixture()
def url(workspace, published_form):
    return (
        f"/api/v1/workspaces/{workspace.id}/forms/{published_form.form_id}/submissions"
    )


async def get(client, url, params=None, user=testUser):
    return await client.get(url, params=params, cookies=cookies(user))


def ids(page) -> list:
    return [item["responseId"] for item in page["items"]]


async def fill(seed, count):
    """``count`` responses a minute apart, oldest first; returns their ids in
    submission order."""
    return [await seed.add(minute) for minute in range(count)]


# -- filters -------------------------------------------------------------------


async def test_the_date_range_is_from_inclusive_to_exclusive(client, seed, url):
    made = await fill(seed, 10)
    page = (
        await get(
            client,
            url,
            {
                "paging": "keyset",
                "submittedFrom": iso(BASE + dt.timedelta(minutes=3)),
                "submittedTo": iso(BASE + dt.timedelta(minutes=7)),
            },
        )
    ).json()
    assert ids(page) == list(reversed(made[3:7]))
    assert page["total"] == 4 and page["totalExact"] is True


async def test_a_date_range_needs_an_offset_and_an_order(client, seed, url):
    naive = await get(client, url, {"submittedFrom": "2026-03-01T00:00:00"})
    assert naive.status_code == 422
    backwards = await get(
        client,
        url,
        {
            "submittedFrom": "2026-03-02T00:00:00Z",
            "submittedTo": "2026-03-01T00:00:00Z",
        },
    )
    assert backwards.status_code == 422
    garbage = await get(client, url, {"submittedFrom": "not a date"})
    assert garbage.status_code == 422


async def test_anonymous_and_known(client, seed, url):
    anonymous = [await seed.add(0), await seed.add(1, owner="")]
    known = [
        await seed.add(2, owner="a@example.com"),
        await seed.add(3, owner="b@example.com"),
    ]
    only_anonymous = (await get(client, url, {"respondent": "anonymous"})).json()
    only_known = (await get(client, url, {"respondent": "known"})).json()
    assert set(ids(only_anonymous)) == set(anonymous)
    assert set(ids(only_known)) == set(known)


async def test_form_version(client, seed, url):
    v1 = [await seed.add(0, version=1), await seed.add(1, version=1)]
    v2 = [await seed.add(2, version=2)]
    v3 = [await seed.add(3, version=3)]
    assert set(ids((await get(client, url, {"formVersion": 1})).json())) == set(v1)
    both = (await get(client, url, {"formVersion": [2, 3]})).json()
    assert set(ids(both)) == set(v2 + v3)
    assert (await get(client, url, {"formVersion": -1})).status_code == 422


async def test_deletion_request_status(client, seed, url):
    none = await seed.add(0)
    pending = await seed.add(
        1, owner="p@example.com", status=DeletionRequestStatus.PENDING
    )
    declined = await seed.add(
        2, owner="d@example.com", status=DeletionRequestStatus.DECLINED
    )

    def listed(page):
        return set(ids(page))

    assert listed((await get(client, url, {"status": "none"})).json()) == {none}
    assert listed((await get(client, url, {"status": "pending"})).json()) == {pending}
    assert listed((await get(client, url, {"status": "declined"})).json()) == {declined}
    two = (await get(client, url, {"status": ["pending", "none"]})).json()
    assert listed(two) == {none, pending}
    assert (await get(client, url, {"status": "bogus"})).status_code == 422
    # the status each row shows is unchanged
    everyone = (await get(client, url, {"paging": "keyset"})).json()
    by_id = {item["responseId"]: item.get("status") for item in everyone["items"]}
    assert by_id[pending] == "pending" and by_id[declined] == "declined"
    assert by_id[none] is None


async def test_the_filters_combine_with_each_other_and_with_the_search(
    client, seed, url
):
    await seed.add(0, owner="ann@example.com", version=1)
    keep = await seed.add(1, owner="ann@example.com", version=2)
    await seed.add(2, owner="bob@example.com", version=2)
    await seed.add(3, version=2)
    page = (
        await get(
            client,
            url,
            {
                "dataOwnerIdentifier": "ANN",
                "formVersion": 2,
                "respondent": "known",
                "submittedFrom": iso(BASE),
            },
        )
    ).json()
    assert ids(page) == [keep]
    assert page["total"] == 1


async def test_a_filter_that_matches_nothing_is_an_empty_exact_page(client, seed, url):
    await fill(seed, 3)
    page = (await get(client, url, {"formVersion": 9})).json()
    assert page["items"] == [] and page["total"] == 0
    assert page["totalExact"] is True and page["hasNext"] is False


async def test_the_list_never_carries_a_plaintext_answer_filter(client, seed, url):
    await fill(seed, 2)
    # an answer is not a column: asking for one finds nothing, it never
    # becomes SQL, and the answers that do come back are decrypted by the server
    page = (await get(client, url, {"q1": SECRET_ANSWER, "paging": "keyset"})).json()
    assert page["total"] == 2


# -- sort and size ----------------------------------------------------------


async def test_sort_by_submitted_time_both_ways(client, seed, url):
    made = await fill(seed, 6)
    newest = (await get(client, url, {"paging": "keyset"})).json()
    assert ids(newest) == list(reversed(made))
    oldest = (
        await get(
            client,
            url,
            {"sort_by": "created_at", "sort_order": "ASCENDING", "paging": "keyset"},
        )
    ).json()
    assert ids(oldest) == made


async def test_sort_by_form_version_then_time(client, seed, url):
    a = await seed.add(0, version=2)
    b = await seed.add(1, version=1)
    c = await seed.add(2, version=2)
    d = await seed.add(3, version=1)
    ascending = (
        await get(
            client,
            url,
            {"paging": "keyset", "sort_by": "form_version", "sort_order": "ASCENDING"},
        )
    ).json()
    assert ids(ascending) == [b, d, a, c]
    descending = (
        await get(client, url, {"paging": "keyset", "sort_by": "form_version"})
    ).json()
    assert ids(descending) == [c, a, d, b]


async def test_only_indexed_sorts_are_served_by_the_keyset_list(client, seed, url):
    await fill(seed, 2)
    refused = await get(client, url, {"sort_by": "answers", "formVersion": 1})
    assert refused.status_code == 400
    # without a keyset parameter the old behaviour stays (offset paging)
    assert (await get(client, url, {"sort_by": "response_id"})).status_code == 200


@pytest.mark.parametrize("size", [25, 50, 100])
async def test_page_sizes(client, seed, url, size):
    await fill(seed, 3)
    page = (await get(client, url, {"paging": "keyset", "size": size})).json()
    assert page["size"] == size and len(page["items"]) == 3


async def test_a_page_size_above_one_hundred_is_refused(client, seed, url):
    assert (
        await get(client, url, {"paging": "keyset", "size": 101})
    ).status_code == 422


# -- keyset paging --------------------------------------------------------------


async def test_next_pages_by_cursor_cover_every_row_once(client, seed, url):
    made = await fill(seed, 60)
    params = {"paging": "keyset", "size": 25, "sort_order": "ASCENDING"}
    seen, cursor, page_number = [], None, 1
    while True:
        query = {
            **params,
            "page": page_number,
            **({"cursor": cursor} if cursor else {}),
        }
        page = (await get(client, url, query)).json()
        seen += ids(page)
        assert page["page"] == page_number
        assert page["total"] == 60 and page["pages"] == 3
        cursor = page["cursor"]
        assert cursor
        if not page["hasNext"]:
            break
        page_number += 1
    assert seen == made
    assert page_number == 3


async def test_previous_and_nearby_pages_by_cursor(client, seed, url):
    made = await fill(seed, 100)
    newest_first = list(reversed(made))
    size = 10
    params = {"paging": "keyset", "size": size}
    # stand on page 6, then go to 5 (previous), 7 (next), 3 and 9 (nearby), 1
    page6 = (await get(client, url, {**params, "page": 6})).json()
    assert ids(page6) == newest_first[50:60]
    for target in (5, 7, 3, 9, 1, 10):
        other = (
            await get(
                client, url, {**params, "page": target, "cursor": page6["cursor"]}
            )
        ).json()
        assert ids(other) == newest_first[(target - 1) * size : target * size], target
        assert other["page"] == target
        assert other["hasNext"] is (target < 10)


async def test_the_last_page_and_pages_near_the_end_without_a_cursor(
    client, seed, url, monkeypatch
):
    made = await fill(seed, 47)
    newest_first = list(reversed(made))
    # starting from the first row would be too far: the end is the way
    monkeypatch.setattr(response_paging, "MAX_OFFSET", 7)
    last = (await get(client, url, {"paging": "keyset", "size": 10, "page": 5})).json()
    assert ids(last) == newest_first[40:47]
    assert last["hasNext"] is False and last["total"] == 47
    near = (await get(client, url, {"paging": "keyset", "size": 10, "page": 4})).json()
    assert ids(near) == newest_first[30:40]
    assert near["hasNext"] is True


async def test_a_page_past_the_end_is_empty(client, seed, url):
    await fill(seed, 12)
    page = (await get(client, url, {"paging": "keyset", "size": 10, "page": 4})).json()
    assert page["items"] == [] and page["hasNext"] is False and not page.get("cursor")


async def test_a_page_too_deep_to_reach_says_so(client, seed, url, monkeypatch):
    await fill(seed, 30)
    monkeypatch.setattr(response_paging, "MAX_OFFSET", 5)
    monkeypatch.setattr(
        responses_module, "COUNT_CAP", 20
    )  # no exact total: no end seek
    refused = await get(client, url, {"paging": "keyset", "size": 10, "page": 3})
    assert refused.status_code == 400
    assert refused.json()["code"] == "page_too_deep"


async def test_a_capped_total_is_a_lower_bound(client, seed, url, monkeypatch):
    made = await fill(seed, 30)
    monkeypatch.setattr(responses_module, "COUNT_CAP", 20)
    page = (await get(client, url, {"paging": "keyset", "size": 10})).json()
    assert page["total"] == 20 and page["totalExact"] is False
    assert page["hasNext"] is True
    # the cursor still walks past the cap
    third = (
        await get(
            client,
            url,
            {"paging": "keyset", "size": 10, "page": 2, "cursor": page["cursor"]},
        )
    ).json()
    fourth = (
        await get(
            client,
            url,
            {"paging": "keyset", "size": 10, "page": 3, "cursor": third["cursor"]},
        )
    ).json()
    assert ids(fourth) == list(reversed(made))[20:30]
    assert fourth["hasNext"] is False


async def test_rows_sharing_a_time_keep_a_stable_order_across_pages(client, seed, url):
    same = [await seed.add(5) for _ in range(7)]  # one submission time
    seen, cursor = [], None
    for page_number in (1, 2, 3):
        page = (
            await get(
                client,
                url,
                {
                    "paging": "keyset",
                    "size": 3,
                    "page": page_number,
                    **({"cursor": cursor} if cursor else {}),
                },
            )
        ).json()
        seen += ids(page)
        cursor = page["cursor"]
    assert sorted(seen) == sorted(same) and len(set(seen)) == 7


async def test_paging_by_version_sort_with_a_cursor(client, seed, url):
    made = []
    for minute in range(12):
        made.append(await seed.add(minute, version=1 + minute % 3))
    expected = sorted(
        range(12), key=lambda m: (-(1 + m % 3), -m)
    )  # version desc, then newest first
    params = {"paging": "keyset", "size": 5, "sort_by": "form_version"}
    first = (await get(client, url, params)).json()
    second = (
        await get(client, url, {**params, "page": 2, "cursor": first["cursor"]})
    ).json()
    third = (
        await get(client, url, {**params, "page": 3, "cursor": second["cursor"]})
    ).json()
    got = ids(first) + ids(second) + ids(third)
    assert got == [made[m] for m in expected]


# -- cursor: tampered, foreign, stale ------------------------------------------


async def first_cursor(client, url, **extra):
    page = (await get(client, url, {"paging": "keyset", "size": 10, **extra})).json()
    assert page["cursor"]
    return page["cursor"]


async def test_a_tampered_cursor_is_refused(client, seed, url):
    await fill(seed, 30)
    cursor = await first_cursor(client, url)
    head, payload, signature = cursor.split(".")
    flipped = "A" if signature[0] != "A" else "B"
    for tampered in (
        f"{head}.{payload}.{flipped}{signature[1:]}",
        f"{head}.{payload[:-2]}xx.{signature}",
        f"{head}.{payload}",
        "x" * 40,
        "",
        "'; DROP TABLE app.form_responses; --",
        cursor + "." + cursor,
    ):
        refused = await get(
            client, url, {"paging": "keyset", "size": 10, "page": 2, "cursor": tampered}
        )
        # an empty value is "no cursor"; the rest are refused
        if tampered == "":
            assert refused.status_code == 200
        else:
            assert refused.status_code == 400, tampered
            assert refused.json()["code"] == "invalid_cursor"
    ok = await get(
        client, url, {"paging": "keyset", "size": 10, "page": 2, "cursor": cursor}
    )
    assert ok.status_code == 200


async def test_a_cursor_signed_with_another_secret_is_refused(
    client, seed, url, monkeypatch
):
    await fill(seed, 30)
    cursor = await first_cursor(client, url)
    monkeypatch.setattr(response_cursor, "_PURPOSE", b"another-purpose")
    refused = await get(
        client, url, {"paging": "keyset", "size": 10, "page": 2, "cursor": cursor}
    )
    assert refused.status_code == 400


async def test_a_cursor_of_another_form_is_refused(
    client, seed, url, workspace, monkeypatch
):
    await fill(seed, 30)
    cursor = await first_cursor(client, url)
    other = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), testUser
    )
    other_url = f"/api/v1/workspaces/{workspace.id}/forms/{other.form_id}/submissions"
    refused = await get(
        client, other_url, {"paging": "keyset", "size": 10, "page": 2, "cursor": cursor}
    )
    assert refused.status_code == 400
    assert refused.json()["code"] == "invalid_cursor"


async def test_a_cursor_only_works_for_the_list_it_was_issued_for(client, seed, url):
    await fill(seed, 30)
    cursor = await first_cursor(client, url)
    base = {"paging": "keyset", "page": 2, "cursor": cursor}
    for changed in (
        {"size": 25},  # another page size
        {"size": 10, "sort_order": "ASCENDING"},
        {"size": 10, "sort_by": "form_version"},
        {"size": 10, "respondent": "known"},
        {"size": 10, "formVersion": 1},
        {"size": 10, "status": "none"},
        {"size": 10, "submittedFrom": iso(BASE)},
        {"size": 10, "dataOwnerIdentifier": "a"},
    ):
        refused = await get(client, url, {**base, **changed})
        assert refused.status_code == 400, changed


async def test_a_cursor_of_another_workspace_is_refused(
    client, seed, url, workspace_1, published_form_1
):
    await fill(seed, 30)
    cursor = await first_cursor(client, url)
    other = (
        f"/api/v1/workspaces/{workspace_1.id}/forms/{published_form_1.form_id}"
        "/submissions"
    )
    refused = await get(
        client,
        other,
        {"paging": "keyset", "size": 10, "page": 2, "cursor": cursor},
        user=testUser1,
    )
    assert refused.status_code == 400


def test_an_expired_cursor_is_refused():
    query = response_cursor.ResponseListQuery(size=10)
    anchor = response_cursor.Anchor(
        page=1, version=None, created_at=BASE, row_id="0" * 24
    )
    token = response_cursor.issue("w", "f", query, anchor, now=BASE)
    assert response_cursor.read(token, "w", "f", query, now=BASE) == anchor
    later = BASE + response_cursor.TOKEN_TTL + dt.timedelta(minutes=1)
    with pytest.raises(response_cursor.InvalidCursor):
        response_cursor.read(token, "w", "f", query, now=later)
    with pytest.raises(response_cursor.InvalidCursor):
        response_cursor.read(token, "w", "f", query, now=BASE - dt.timedelta(hours=1))


def test_a_signed_cursor_with_a_bad_value_is_still_refused():
    """The values are checked again after the signature (defence in depth)."""
    import base64
    import hashlib
    import hmac
    import json

    query = response_cursor.ResponseListQuery(size=10)
    claims = response_cursor._binding("w", "f", query)
    good = {
        **claims,
        "p": 2,
        "t": BASE.isoformat(),
        "r": "a" * 24,
        "i": int(BASE.timestamp() * 1000),
    }

    def signed(overrides):
        payload = (
            base64.urlsafe_b64encode(json.dumps({**good, **overrides}).encode())
            .rstrip(b"=")
            .decode()
        )
        body = f"c1.{payload}"
        key, text = response_cursor._key(), response_cursor._signed_text(body, query)
        return f"{body}.{response_cursor._sign(key, text)}"

    assert response_cursor.read(signed({}), "w", "f", query, now=BASE).page == 2
    for bad in (
        {"r": "a'; DROP TABLE x; --"},
        {"r": "A" * 24},
        {"r": 5},
        {"t": "2026-03-01T12:00:00"},  # no offset
        {"t": "now()"},
        {"p": 0},
        {"p": "2"},
        {"p": True},
        {"v": 3},  # a version in a list sorted by time
        {"i": "x"},
    ):
        with pytest.raises(response_cursor.InvalidCursor):
            response_cursor.read(signed(bad), "w", "f", query, now=BASE)


# -- roles ---------------------------------------------------------------------


async def member(workspace, role) -> User:
    user = User(id=str(RecordId()), sub=f"{role.value.lower()}@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
    )
    return user


@pytest.mark.parametrize(
    "role,status",
    [
        (WorkspaceRoles.ADMIN, 200),
        (WorkspaceRoles.EDITOR, 200),
        (WorkspaceRoles.REVIEWER, 200),
        (WorkspaceRoles.VIEWER, 200),
        (WorkspaceRoles.PRIVACY_OFFICER, 403),
    ],
)
async def test_who_may_list_with_filters(client, seed, url, workspace, role, status):
    await fill(seed, 2)
    user = await member(workspace, role)
    response = await get(
        client, url, {"paging": "keyset", "respondent": "anonymous"}, user=user
    )
    assert response.status_code == status, response.text
    if status == 403:
        # a refusal says nothing about the rows (nor the filters' matches)
        assert "total" not in response.text and SECRET_ANSWER not in response.text


async def test_unauthenticated_and_foreign_callers_are_refused(
    client, seed, url, workspace_1
):
    await fill(seed, 1)
    assert (await client.get(url, params={"paging": "keyset"})).status_code == 401
    foreign = await get(client, url, {"paging": "keyset"}, user=testUser1)
    assert foreign.status_code in (403, 404)


async def test_a_form_of_another_workspace_is_not_found(
    client, seed, workspace, workspace_1, published_form_1
):
    other = (
        f"/api/v1/workspaces/{workspace.id}/forms/{published_form_1.form_id}"
        "/submissions"
    )
    response = await get(client, other, {"paging": "keyset"})
    assert response.status_code == 404


async def test_deletion_requests_take_no_filters_or_cursors(client, seed, url):
    refused = await get(
        client, url, {"request_for_deletion": "true", "respondent": "known"}
    )
    assert refused.status_code == 400
    plain = await get(client, url, {"request_for_deletion": "true"})
    assert plain.status_code == 200


async def test_answers_stay_decrypted_by_the_server_only(client, seed, url):
    await seed.add(0, owner="x@example.com")
    page = (await get(client, url, {"paging": "keyset"})).json()
    assert page["items"][0]["answers"]["q1"]["text"] == SECRET_ANSWER
    stored = await seed.repo.get_response(page["items"][0]["responseId"])
    assert SECRET_ANSWER not in str(stored.answers)  # ciphertext at rest


# -- the old behaviour is unchanged --------------------------------------------


async def test_the_list_without_new_parameters_pages_as_before(client, seed, url):
    made = await fill(seed, 7)
    first = (await get(client, url, {"page": 1, "size": 3})).json()
    second = (await get(client, url, {"page": 2, "size": 3})).json()
    assert ids(first) + ids(second) == list(reversed(made))[:6]
    assert first["total"] == 7 and first["pages"] == 3
    assert not first.get("cursor")  # offset paging issues none


# -- the paging plan -----------------------------------------------------------


@pytest.mark.parametrize(
    "page,anchor,exact,source",
    [
        (1, None, True, "start"),
        (3, 2, True, "cursor"),
        (2, 3, True, "cursor"),
        (500, None, True, "end"),  # 500 of 520 pages: nearer the end
        (500, 499, True, "cursor"),
    ],
)
def test_the_plan_takes_the_cheapest_seek(page, anchor, exact, source):
    seek = response_paging.plan(page, 25, 520 * 25, exact, anchor)
    assert seek.source == source


def test_the_plan_refuses_a_page_nothing_reaches():
    with pytest.raises(response_paging.PageTooDeep):
        response_paging.plan(5000, 25, 10_000, False, None)
    with pytest.raises(response_paging.PageTooDeep):
        response_paging.plan(5000, 25, 200_000, False, 4000)  # cursor too far


# -- review fixes --------------------------------------------------------------


def _claims(token: str) -> dict:
    import base64
    import json

    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


async def test_the_cursor_holds_nothing_derived_from_the_search(client, seed, url):
    import hashlib

    await seed.add(0, owner="ann@example.com")
    for minute in range(1, 30):
        await seed.add(minute, owner=f"ann{minute}@example.com")
    search = "ann@example.com"
    page = (
        await get(
            client,
            url,
            {"paging": "keyset", "size": 10, "dataOwnerIdentifier": search},
        )
    ).json()
    cursor = page["cursor"]
    claims = _claims(cursor)
    assert "q" not in claims
    # no claim is the search, a hash of it, or contains either
    candidates = {
        search,
        hashlib.sha256(search.encode()).hexdigest(),
        hashlib.sha256(search.encode()).hexdigest()[:32],
    }
    for value in claims.values():
        assert not any(str(c) in str(value) for c in candidates), value
    assert search not in cursor
    # a different search (or none) refuses the cursor; the same one accepts it
    ok = {"paging": "keyset", "size": 10, "page": 2, "cursor": cursor}
    assert (
        await get(client, url, {**ok, "dataOwnerIdentifier": search})
    ).status_code == 200
    for other in ({"dataOwnerIdentifier": "bob"}, {}):
        assert (await get(client, url, {**ok, **other})).status_code == 400


async def test_a_search_over_320_characters_is_a_422_not_a_500(client, seed, url):
    await fill(seed, 1)
    long = await get(
        client, url, {"paging": "keyset", "dataOwnerIdentifier": "a" * 321}
    )
    assert long.status_code == 422
    fine = await get(
        client, url, {"paging": "keyset", "dataOwnerIdentifier": "a" * 320}
    )
    assert fine.status_code == 200


async def test_sort_order_is_ascending_or_descending(client, seed, url):
    await fill(seed, 2)
    for good in ("ASCENDING", "descending", "asc", "DESC"):
        ok = await get(client, url, {"paging": "keyset", "sort_order": good})
        assert ok.status_code == 200, good
    bad = await get(client, url, {"paging": "keyset", "sort_order": "sideways"})
    assert bad.status_code == 422


async def test_the_status_filter_follows_the_status_a_row_shows(client, seed, url):
    from backend.app.schemas.standard_form_response import (
        FormResponseDeletionRequest,
    )
    from backend.db.models import ResponseDeletionRequestRow

    # two requests for one response (two providers): the row shows the first
    first_pending = await seed.add(
        0, owner="a@example.com", status=DeletionRequestStatus.PENDING
    )
    stored = await seed.repo.get_response(first_pending)
    await seed.repo.save_document(
        FormResponseDeletionRequest(
            form_id=stored.form_id,
            response_id=first_pending,
            provider="other",
            workspace_id=stored.workspace_id,
            status=DeletionRequestStatus.DECLINED,
        ),
        row=ResponseDeletionRequestRow,
    )
    page = (await get(client, url, {"paging": "keyset"})).json()
    assert page["items"][0]["status"] == "pending"
    assert ids((await get(client, url, {"status": "pending"})).json()) == [
        first_pending
    ]
    assert (await get(client, url, {"status": "declined"})).json()["items"] == []
    assert (await get(client, url, {"status": "none"})).json()["items"] == []


async def test_the_range_keeps_sub_second_precision(client, seed, url):
    early = await seed.add(0, micro=100_000)
    late = await seed.add(0, micro=500_000)
    t = BASE
    # from 0.25 s: only the later; to exactly 0.5 s (exclusive): only the earlier
    page = (
        await get(
            client,
            url,
            {"submittedFrom": iso(t + dt.timedelta(microseconds=250_000))},
        )
    ).json()
    assert ids(page) == [late]
    page = (
        await get(
            client,
            url,
            {"submittedTo": iso(t + dt.timedelta(microseconds=500_000))},
        )
    ).json()
    assert ids(page) == [early]
    exact = (
        await get(
            client,
            url,
            {"submittedFrom": iso(t + dt.timedelta(microseconds=500_000))},
        )
    ).json()
    assert ids(exact) == [late]


async def test_form_version_zero_matches_responses_without_one(client, seed, url):
    none = await seed.add(0, version=None)
    await seed.add(1, version=2)
    assert ids((await get(client, url, {"formVersion": 0})).json()) == [none]


async def test_a_response_without_a_submission_time_does_not_break_the_list(
    client, seed, url
):
    from sqlalchemy import text

    made = await fill(seed, 5)
    async with container.pg_engine().begin() as connection:
        await connection.execute(
            text(
                "UPDATE app.form_responses SET created_at = NULL WHERE response_id = :r"
            ),
            {"r": made[0]},
        )
    page = (await get(client, url, {"paging": "keyset", "size": 10})).json()
    assert set(ids(page)) == set(made[1:]) and page["total"] == 4
    assert page["cursor"]
