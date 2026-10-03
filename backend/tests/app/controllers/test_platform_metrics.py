"""The platform metrics endpoint: platform admins only, aggregates only, user
counts from the auth service (forwarding the admin's token), a partial result
when auth cannot answer, and a one-minute cache."""

import datetime as dt

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.services.platform_metrics_service import week_starts
from common.exceptions.http import HTTPException as CommonHTTPException
from tests.app.controllers.data import testUser

URL = "/api/v1/admin/metrics"


class FakeAuthClient:
    """Stands in for the HttpClient the service calls the auth service with."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    async def get(self, url, params=None, headers=None, **kwargs):
        self.calls.append({"url": url, "params": params, "headers": headers})
        if self.fail:
            raise CommonHTTPException(503, "Requested Source not available.")
        first = dt.date.fromisoformat(params["first_week"])
        return {
            "total": 10,
            "new_last_30_days": 4,
            "active_last_30_days": 6,
            "by_plan": {"FREE": 8, "PRO": 2},
            "weekly_new": [
                {"week_start": (first + dt.timedelta(weeks=i)).isoformat(), "count": i}
                for i in range(params["weeks"])
            ],
        }


@pytest.fixture
def metrics_service():
    service = container.platform_metrics_service()
    service.clear_cache()
    yield service
    service.clear_cache()


@pytest.fixture
def auth_ok(metrics_service, monkeypatch):
    fake = FakeAuthClient()
    monkeypatch.setattr(metrics_service, "_http_client", fake)
    return fake


@pytest.fixture
def auth_down(metrics_service, monkeypatch):
    fake = FakeAuthClient(fail=True)
    monkeypatch.setattr(metrics_service, "_http_client", fake)
    return fake


async def test_requires_login(client: AsyncClient, auth_ok):
    response = await client.get(URL)
    assert response.status_code == 401
    assert auth_ok.calls == []


async def test_is_platform_admin_only(
    client: AsyncClient, test_user_cookies_1, auth_ok
):
    response = await client.get(URL, cookies=test_user_cookies_1)
    assert response.status_code == 403
    assert auth_ok.calls == []


async def test_admin_gets_counts(
    client: AsyncClient, test_user_cookies, workspace_form_response, auth_ok
):
    assert testUser.is_admin()
    response = await client.get(URL, cookies=test_user_cookies)
    assert response.status_code == 200
    body = response.json()

    assert body["organizations"] == {"total": 1, "newLast30Days": 1, "disabled": 0}
    assert body["forms"] == {
        "total": 1,
        "published": 1,
        "newLast30Days": 1,
        "byProvider": {"self": 1},
    }
    assert body["formCreators"] == {"total": 1, "activeLast30Days": 1}
    assert body["responses"] == {"total": 1, "last7Days": 1, "last30Days": 1}
    responders = body["formResponders"]
    assert responders["identified"] + responders["anonymousResponses"] == 1
    assert body["users"] == {
        "total": 10,
        "newLast30Days": 4,
        "activeLast30Days": 6,
        "byPlan": {"FREE": 8, "PRO": 2},
    }
    assert body["errors"] == []

    weekly = body["weekly"]
    weeks = week_starts(dt.datetime.now(dt.timezone.utc))
    assert [w["weekStart"] for w in weekly] == [w.date().isoformat() for w in weeks]
    assert [w["newUsers"] for w in weekly] == list(range(12))
    assert weekly[-1]["newOrganizations"] == 1
    assert weekly[-1]["newForms"] == 1
    assert weekly[-1]["responses"] == 1
    assert sum(w["responses"] for w in weekly[:-1]) == 0

    # the admin's own token went to auth, with the charted weeks
    (call,) = auth_ok.calls
    assert call["url"].endswith("/admin/metrics")
    assert call["headers"] == {
        "Authorization": f"Bearer {test_user_cookies['Authorization']}"
    }
    assert call["params"] == {"first_week": weeks[0].date().isoformat(), "weeks": 12}

    # nothing identifying in the payload
    assert testUser.sub not in response.text


async def test_auth_down_returns_the_rest(
    client: AsyncClient, test_user_cookies, workspace, auth_down
):
    response = await client.get(URL, cookies=test_user_cookies)
    assert response.status_code == 200
    body = response.json()
    assert body["users"] is None
    assert [e["source"] for e in body["errors"]] == ["users"]
    assert body["organizations"]["total"] == 1
    assert all(w["newUsers"] is None for w in body["weekly"])

    # a partial result is not cached: the next request asks auth again
    await client.get(URL, cookies=test_user_cookies)
    assert len(auth_down.calls) == 2


async def test_result_is_cached(
    client: AsyncClient, test_user_cookies, workspace, auth_ok
):
    first = await client.get(URL, cookies=test_user_cookies)
    second = await client.get(URL, cookies=test_user_cookies)
    assert first.json() == second.json()
    assert len(auth_ok.calls) == 1

    container.platform_metrics_service().clear_cache()
    third = await client.get(URL, cookies=test_user_cookies)
    assert len(auth_ok.calls) == 2
    assert third.json()["generatedAt"] != first.json()["generatedAt"]
