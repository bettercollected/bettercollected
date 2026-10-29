"""Answer patterns on a form, checked when it is saved
(services/form_patterns.py): the server matches them with RE2, which has no
lookarounds and no backreferences, so a pattern RE2 cannot use is refused with
422 ``invalid_pattern`` naming the question and the reason; one the stored
draft already holds is kept so such a form can still be edited; a copy drops
it. A pattern RE2 can use is saved however it is shaped (``(a+)+`` included):
RE2 runs in linear time and the respondent's browser never runs it. Nothing
here analyses a pattern's shape, so nothing here can take long."""

import json
import time
from typing import Any, Coroutine

import pytest
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.form_patterns import check_form_patterns

API = "/api/v1"
UNSAFE = "^(?=a)b$"  # a lookahead: RE2 has none
SAFE = "^[A-Za-z]+( [A-Za-z]+)*$"
# 117 characters of nested repeats: a shape analysis took 29 s and 2 GB on it
NESTED = "^" + "(?:" * 16 + "a*b" + "){3}" * 16 + "$"


def form_url(workspace, form) -> str:
    return f"{API}/workspaces/{workspace.id}/forms/{form.form_id}"


def with_pattern(pattern, other=None):
    return {
        "title": "Patterns",
        "builder_version": "v2",
        "fields": [
            {
                "id": "page-1",
                "index": 0,
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "q-1",
                            "index": 0,
                            "type": "short_text",
                            "title": "Name",
                            "validations": {"regex": pattern},
                        },
                        {
                            "id": "q-2",
                            "index": 1,
                            "type": "short_text",
                            "title": "Other",
                            "validations": {"regex": other},
                        },
                    ]
                },
            }
        ],
    }


async def patch(client, workspace, form, cookies, body: dict):
    return await client.patch(
        form_url(workspace, form),
        cookies=cookies,
        data={"form_body": json.dumps(body)},
    )


async def stored(form) -> FormDocument:
    return await container.form_service().get_form_document_by_id(form.form_id)


def regexes(form):
    return [q.validations.regex for q in form.fields[0].properties.fields]


async def test_a_pattern_re2_cannot_use_is_refused_on_save_with_the_question_and_the_reason(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(None, UNSAFE)
    )
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "invalid_pattern"
    assert [e["fieldId"] for e in body["errors"]] == ["q-2"]
    assert "invalid perl operator" in body["message"]
    assert "no lookarounds and no backreferences" in body["message"]
    assert UNSAFE not in json.dumps(
        (await stored(workspace_form)).model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "pattern, reason",
    [
        (r"(a)\1", "invalid escape sequence"),
        ("(a+", "missing )"),
        ("[a-", "missing ]"),
        ("^(?<=a)b$", "invalid"),
    ],
)
async def test_each_kind_of_unusable_pattern_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    pattern,
    reason,
):
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(pattern)
    )
    assert response.status_code == 422, response.text
    assert response.json()["errors"][0]["fieldId"] == "q-1"
    assert reason in response.json()["message"]


async def test_a_safe_pattern_is_stored(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(SAFE)
    )
    assert response.status_code == 200, response.text
    assert regexes(await stored(workspace_form)) == [SAFE, None]


async def test_a_backtracking_shape_is_no_reason_to_refuse_a_pattern_re2_can_use(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # RE2 matches it in linear time and the browser never runs it
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern("^(a+)+$")
    )
    assert response.status_code == 200, response.text


async def test_a_deeply_nested_pattern_is_dealt_with_in_no_time(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # the check on a save is one bounded RE2 compile, never work that grows
    # with how the pattern is nested
    started = time.perf_counter()
    check_form_patterns(StandardForm(**with_pattern(NESTED)), None, drop=True)
    assert time.perf_counter() - started < 0.5
    started = time.perf_counter()
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(NESTED)
    )
    assert time.perf_counter() - started < 2  # the request, not just the check
    assert response.status_code == 422, response.text  # RE2 will not take it
    assert "invalid repetition size" in response.json()["message"]


async def test_a_pattern_the_form_already_holds_is_kept(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # a form saved before the check, with a pattern RE2 cannot use
    legacy = StandardForm(**with_pattern(UNSAFE))
    legacy.form_id = workspace_form.form_id
    await container.form_service().update_form(
        form_id=workspace_form.form_id, form=legacy
    )

    # saved again with the pattern unchanged (or moved to the other question,
    # the draft holds that exact pattern): kept
    for body in (with_pattern(UNSAFE), with_pattern(None, UNSAFE)):
        response = await patch(
            client, workspace, workspace_form, test_user_cookies, body
        )
        assert response.status_code == 200, response.text
    assert regexes(await stored(workspace_form)) == [None, UNSAFE]

    # a different unusable pattern never gets in, a usable one replaces it
    response = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_pattern(None, "^(?=b)a$"),
    )
    assert response.status_code == 422
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(None, SAFE)
    )
    assert response.status_code == 200, response.text

    # once gone from the form, the old one cannot come back
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(UNSAFE)
    )
    assert response.status_code == 422


async def test_a_new_form_with_an_unusable_pattern_is_refused(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_pattern(UNSAFE))},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_pattern"
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_pattern(SAFE))},
    )
    assert response.status_code == 200, response.text


def test_a_copy_drops_an_unusable_pattern_instead_of_refusing():
    form = StandardForm(**with_pattern(UNSAFE, SAFE))
    check_form_patterns(form, None, drop=True)
    assert regexes(form) == [None, SAFE]


async def test_a_unicode_property_pattern_is_fine(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # \p{L} is RE2 syntax too (Python's re cannot compile it)
    kept = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_pattern(r"^[\p{L} '-]+$"),
    )
    assert kept.status_code == 200, kept.text


async def test_the_builder_can_ask_whether_a_pattern_can_be_saved(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
):
    url = f"{API}/workspaces/{workspace.id}/forms/pattern/check"
    ok = await client.post(url, cookies=test_user_cookies, json={"pattern": SAFE})
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"valid": True, "message": None, "reason": None}
    bad = await client.post(url, cookies=test_user_cookies, json={"pattern": UNSAFE})
    assert bad.json()["valid"] is False
    assert "invalid perl operator" in bad.json()["message"]
    assert bad.json()["reason"] == "invalid perl operator: (?="
    too_long = await client.post(
        url, cookies=test_user_cookies, json={"pattern": "a" * 201}
    )
    assert too_long.json()["valid"] is False
    assert "at most 200" in too_long.json()["message"]
    anonymous = await client.post(url, json={"pattern": SAFE})
    assert anonymous.status_code in (401, 403)
