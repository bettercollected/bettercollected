"""Decrypted response data is sent with ``Cache-Control: no-store`` so a
browser on a shared computer does not keep it."""

import pytest
from httpx import AsyncClient

from backend.app.middlewares.request_privacy import carries_response_data
from tests.app.controllers.test_privacy_officer import (  # noqa: F401
    _cookies,
    officer,
    requested,
)

WS = "/api/v1/workspaces/{ws}"

STAFF_ROUTES = {
    "a form's submissions": WS + "/forms/{form}/submissions",
    "the workspace's submissions": WS + "/all-submissions",
    "the form's deletion requests": WS
    + "/forms/{form}/submissions?request_for_deletion=true",
    "one submission": WS + "/submissions/{response}",
    "a form's all-submissions": WS + "/forms/{form}/all-submissions",
    "the exports of a form": WS + "/forms/{form}/exports",
    "the export columns": WS + "/forms/{form}/exports/columns",
    "the submission paths": WS + "/forms/{form}/submission-paths",
    "the responders": WS + "/responders",
    "the AI insights": WS + "/forms/{form}/ai/insights",
}


def assert_no_store(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


@pytest.mark.parametrize("route", STAFF_ROUTES)
async def test_staff_routes_are_not_cached(
    client: AsyncClient, requested, test_user_cookies, route
):
    response = await client.get(
        STAFF_ROUTES[route].format(**requested), cookies=test_user_cookies
    )

    assert response.status_code == 200, response.text
    assert_no_store(response)


@pytest.mark.parametrize("route", STAFF_ROUTES)
async def test_a_refusal_is_not_cached_either(client: AsyncClient, requested, route):
    """The Privacy officer is refused the answers (the deletion-request list
    aside): whatever comes back is still not kept."""
    response = await client.get(
        STAFF_ROUTES[route].format(**requested), cookies=_cookies(officer)
    )

    assert_no_store(response)


async def test_the_receipt_by_number_is_not_cached(client: AsyncClient, requested):
    from backend.app.container import container

    stored = await container.form_response_repo().get_response(requested["response"])

    response = await client.get(
        (WS + "/submissions/by-uuid/").format(**requested) + stored.submission_uuid
    )

    assert response.status_code == 200, response.text
    assert_no_store(response)
    # an unknown number too
    unknown = await client.get((WS + "/submissions/by-uuid/nope").format(**requested))
    assert unknown.status_code == 404
    assert_no_store(unknown)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workspaces/w/forms/f/submissions",
        "/api/v1/workspaces/w/forms/f/submissions/r1",
        "/api/v1/workspaces/w/all-submissions",
        "/api/v1/workspaces/w/forms/f/all-submissions",
        "/api/v1/workspaces/w/forms/f/exports",
        "/api/v1/workspaces/w/forms/f/exports/columns",
        "/api/v1/workspaces/w/forms/f/exports/abc",
        "/api/v1/workspaces/w/forms/f/exports/abc/download",
        "/api/v1/workspaces/w/forms/f/submission-paths",
        "/api/v1/workspaces/w/submissions/by-uuid/abc",
        "/api/v1/workspaces/w/submissions",
        "/api/v1/workspaces/w/responders",
        "/api/v1/workspaces/w/forms/f/ai/insights",
    ],
)
def test_the_response_data_paths(path):
    assert carries_response_data(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/workspaces/w/forms/f",
        "/api/v1/workspaces/w",
        "/api/v1/workspaces/w/forms/f/all-submissions-x",
        "/api/v1/workspaces/w/forms/f/not-submissions",
        "/api/v1/forms/f/submissions",
    ],
)
def test_other_paths_are_left_alone(path):
    assert not carries_response_data(path)


async def test_generating_ai_insights_is_not_cached(
    client: AsyncClient, requested, test_user_cookies
):
    """The POST that reads the responses and returns the summary (refused here
    while the form has not opted in: whatever it answers is not kept)."""
    response = await client.post(
        (WS + "/forms/{form}/ai/insights").format(**requested),
        cookies=test_user_cookies,
        json={},
    )

    assert_no_store(response)
