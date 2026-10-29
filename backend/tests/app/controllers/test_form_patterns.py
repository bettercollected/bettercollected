"""Answer patterns on a form, checked when it is saved
(services/form_patterns.py): a pattern whose shape can freeze a respondent's
browser (``(a+)+``, a backreference) is refused with 422 ``unsafe_pattern``
naming the question, never the pattern; one the stored draft already holds is
kept so such a form can still be edited; a copy drops it. The shape rules
themselves are in common/tests/test_pattern_safety.py."""

import json
from typing import Any, Coroutine

import pytest
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.form_patterns import check_form_patterns

API = "/api/v1"
UNSAFE = "^(a+)+$"
SAFE = "^[A-Za-z]+( [A-Za-z]+)*$"


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


async def test_an_unsafe_pattern_is_refused_on_save_with_the_question_and_no_pattern(
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
    assert body["code"] == "unsafe_pattern"
    assert body["errors"] == [{"fieldId": "q-2", "hazard": "nested_repeat"}]
    assert "repeated group" in body["message"]
    assert UNSAFE not in response.text
    assert UNSAFE not in json.dumps(
        (await stored(workspace_form)).model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "pattern, hazard",
    [
        ("^(a|aa)+$", "overlapping_alternatives"),
        (r"(a)\1", "backreference"),
        (r"^\d*\d*\d*$", "adjacent_repeats"),
        (r"^(a?|b?){28}a{28}$", "nested_repeat"),
        (r"^.*a.*a.*a.*a.*a.*a.*a.*a$", "adjacent_repeats"),
        (r"^(?i)abc$", "inline_flags"),
        (r"a*(?:b|a*)(?:c|a*)x", "adjacent_repeats"),
        (r"a{1,99}a{1,99}a{1,99}!", "adjacent_repeats"),
        (r"\d*\d*x", "adjacent_repeats"),
    ],
)
async def test_each_hazard_is_refused_with_its_code(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
    pattern,
    hazard,
):
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(pattern)
    )
    assert response.status_code == 422, response.text
    assert response.json()["errors"] == [{"fieldId": "q-1", "hazard": hazard}]


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


async def test_a_pattern_the_form_already_holds_is_kept(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # a form saved before the check, with an unsafe pattern on one question
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

    # a different unsafe pattern never gets in, a safe one replaces it
    response = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_pattern(None, "^(b+)+$"),
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


async def test_a_new_form_with_an_unsafe_pattern_is_refused(
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
    assert response.json()["code"] == "unsafe_pattern"
    response = await client.post(
        f"{API}/workspaces/{workspace.id}/forms",
        cookies=test_user_cookies,
        data={"form_body": json.dumps(with_pattern(SAFE))},
    )
    assert response.status_code == 200, response.text


def test_a_copy_drops_an_unsafe_pattern_instead_of_refusing():
    form = StandardForm(**with_pattern(UNSAFE, SAFE))
    check_form_patterns(form, None, drop=True)
    assert regexes(form) == [None, SAFE]


async def test_a_pattern_that_does_not_compile_is_still_saved_while_it_is_typed(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # the builder saves "(a+" on the way to "(a+)": nothing evaluates it
    response = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern("(a+")
    )
    assert response.status_code == 200, response.text
    assert regexes(await stored(workspace_form)) == ["(a+", None]


async def test_a_unicode_property_pattern_is_checked_though_python_cannot_compile_it(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # \p{L} is fine for the browser and RE2: the shape is what matters
    refused = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_pattern(r"^(\p{L}+\s?)+$"),
    )
    assert refused.status_code == 422, refused.text
    kept = await patch(
        client,
        workspace,
        workspace_form,
        test_user_cookies,
        with_pattern(r"^[\p{L} '-]+$"),
    )
    assert kept.status_code == 200, kept.text


async def test_a_pattern_that_starts_with_a_caret_may_hold_more_repeats(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
    test_user_cookies: dict[str, str],
):
    # tried at every start of an answer, \d*\d*x is refused; anchored, it is
    # a limited amount of work and kept
    refused = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(r"\d*\d*x")
    )
    assert refused.status_code == 422, refused.text
    kept = await patch(
        client, workspace, workspace_form, test_user_cookies, with_pattern(r"^\d*\d*x$")
    )
    assert kept.status_code == 200, kept.text
