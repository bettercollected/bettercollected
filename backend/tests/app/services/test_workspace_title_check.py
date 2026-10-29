"""A form is not published while its workspace has no title
(services/publish_checks.py ``workspace_title_problem``): respondents see the
workspace's title as who receives their answers. Every way of publishing
refuses with the existing ``form_not_publishable`` error and one problem,
``workspace_title_missing``, which carries nothing of the workspace.

Only forms created under check version 2 or later are held to it
(``requires_workspace_title``, like "why we ask" from version 1): a form made
earlier publishes and republishes as it always did."""

import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
)

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.publish_checks import (
    FORM_NOT_PUBLISHABLE,
    MISSING_WHY_WE_ASK,
    PUBLISH_CHECKS_VERSION,
    WORKSPACE_TITLE_MISSING,
    ensure_publishable,
    has_workspace_title,
    requires_why_we_ask,
    requires_workspace_title,
    workspace_title_problem,
)
from tests.app.controllers.data import testUser
from tests.app.controllers.test_mcp_server import _call_tool, _make_key
from tests.app.controllers.test_public_api import BASE, _auth, _create, _token

def _form(question_type=T.SHORT_TEXT) -> StandardForm:
    return StandardForm(
        title="Sign-up",
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(
                    fields=[
                        StandardFormField(
                            id="q",
                            type=question_type,
                            title="Your name",
                            properties=StandardFieldProperty(fields=[]),
                        )
                    ]
                ),
            )
        ],
    )


async def _draft(workspace, question_type=T.SHORT_TEXT) -> str:
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(question_type), testUser
    )
    return form.form_id


async def _set_title(workspace, title):
    await container.workspace_repo().set_fields(workspace, {"title": title})


async def _set_checks_version(workspace, form_id, version):
    """Make the form as created under an older check version (None: before
    the checks existed)."""
    repo = container.workspace_form_repo()
    workspace_form = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form_id)
    )
    workspace_form.settings.publish_checks_version = version
    await repo.save(workspace_form)


async def _rename_draft(form_id, title):
    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.title = title
    await container.form_service().update_form(form_id=form_id, form=draft)


async def _publish(workspace, form_id):
    return await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )


async def _latest(form_id):
    return await container.form_repo().get_latest_version_of_form(form_id)


def _only_problem(content) -> dict:
    assert content["code"] == FORM_NOT_PUBLISHABLE
    assert [p["code"] for p in content["problems"]] == [WORKSPACE_TITLE_MISSING]
    return content["problems"][0]


# ---------------------------------------------------------------- the rule


INVISIBLE_ONLY = [
    "\u200b",  # zero-width space
    "\u2060",  # word joiner
    "\ufeff",  # byte order mark
    "\u3164",  # Hangul filler
    "\u115f\u1160",
    "\uffa0",
    "\u2800",  # Braille blank
    "\u00ad",  # soft hyphen
    "\u180e",
    "\u2028\u2029",
    "\u0000\u0007",
    " \u200b \u3164\n\t\ufeff\u00a0 ",  # mixed invisible and whitespace
]
PLACEHOLDERS = ["untitled", "Untitled", "UNTITLED", "  Untitled \n", "un\u200btitled"]


@pytest.mark.parametrize(
    "title",
    [None, "", " ", "   ", "\t", "\n", "\u00a0", *INVISIBLE_ONLY, *PLACEHOLDERS],
)
def test_a_missing_or_blank_title_is_a_problem(title):
    problem = workspace_title_problem(title)
    assert problem is not None
    assert problem["code"] == WORKSPACE_TITLE_MISSING
    assert problem["fieldId"] is None


@pytest.mark.parametrize(
    "title",
    [
        "Acme Foundation",
        "A",
        "  Acme  ",
        "Café de Vries",
        "\u200bA\u3164",  # one visible character among invisible ones
        " \u200b \u3164\n\ufeffx\u2060 ",
        "Untitled workspace",  # only the bare placeholder is no title
        "untitled-2",
        "Ünïcode 名前",
    ],
)
def test_a_real_title_is_no_problem(title):
    assert workspace_title_problem(title) is None


_CASES = json.loads(
    (
        Path(__file__).resolve().parents[4] / "docs/spec/workspace-title.cases.json"
    ).read_text(encoding="utf-8")
)


@pytest.mark.parametrize("title", _CASES["refused"])
def test_the_shared_cases_that_are_no_title(title):
    """The cases the webapp's publish-checks.test.ts runs too: the builder's
    check and the server's agree."""
    assert has_workspace_title(title) is False


@pytest.mark.parametrize("title", _CASES["accepted"])
def test_the_shared_cases_that_are_a_title(title):
    assert has_workspace_title(title) is True


def test_the_problem_names_nothing_of_the_workspace():
    """The shape is fixed: a code, an empty field id and a sentence, with no
    argument that could carry the workspace's id, handle, title or owner."""
    problem = workspace_title_problem("")
    assert set(problem) == {"code", "fieldId", "message"}
    assert "settings" in problem["message"]


def test_ensure_publishable_lists_it_after_the_review_problem_and_before_the_rest():
    review = {"code": "needs_review", "fieldId": None, "message": "review"}
    form = _form(T.EMAIL)
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(
            form,
            checks_version=PUBLISH_CHECKS_VERSION,
            review=review,
            workspace_problem=workspace_title_problem(""),
        )
    codes = [p["code"] for p in raised.value.content["problems"]]
    assert codes == ["needs_review", WORKSPACE_TITLE_MISSING, MISSING_WHY_WE_ASK]


def test_a_titled_workspace_adds_no_problem():
    ensure_publishable(
        _form(),
        checks_version=PUBLISH_CHECKS_VERSION,
        workspace_problem=workspace_title_problem("Acme"),
    )


# ------------------------------------------ which forms are held to the rule


def test_the_rule_starts_at_version_2_and_new_forms_are_created_under_it():
    assert PUBLISH_CHECKS_VERSION == 2
    assert [requires_workspace_title(v) for v in (None, 0, 1, 2, 3)] == [
        False,
        False,
        False,
        True,
        True,
    ]


def test_the_version_bump_leaves_why_we_ask_as_it_was():
    assert [requires_why_we_ask(v) for v in (None, 0, 1, 2, 3)] == [
        False,
        False,
        True,
        True,
        True,
    ]


@pytest.mark.parametrize("version", [None, 0, 1])
def test_an_older_form_is_not_held_to_the_title(version):
    ensure_publishable(
        _form(), checks_version=version, workspace_problem=workspace_title_problem("")
    )


@pytest.mark.parametrize("version", [2, 3])
def test_a_form_under_the_rule_is_held_to_the_title(version):
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(
            _form(),
            checks_version=version,
            workspace_problem=workspace_title_problem(""),
        )
    assert [p["code"] for p in raised.value.content["problems"]] == [
        WORKSPACE_TITLE_MISSING
    ]


@pytest.mark.parametrize(
    ("version", "expected"),
    [(None, []), (1, [MISSING_WHY_WE_ASK]), (2, [MISSING_WHY_WE_ASK])],
)
def test_the_other_checks_do_not_change_with_the_version(version, expected):
    """With a titled workspace, an email question without a reason is refused
    exactly as before for every version (and passes for a form older than
    the reason rule)."""
    workspace_problem = workspace_title_problem("Acme")
    if not expected:
        ensure_publishable(
            _form(T.EMAIL), checks_version=version, workspace_problem=workspace_problem
        )
        return
    with pytest.raises(HTTPException) as raised:
        ensure_publishable(
            _form(T.EMAIL), checks_version=version, workspace_problem=workspace_problem
        )
    assert [p["code"] for p in raised.value.content["problems"]] == expected


# ----------------------------------------------------------- the service


async def test_publish_is_refused_in_an_untitled_workspace(untitled_workspace):
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    assert raised.value.status_code == 422
    _only_problem(raised.value.content)
    assert await _latest(form_id) is None


@pytest.mark.parametrize(
    "title",
    ["", " ", "   ", "\t\n", "\u200b", "\u3164", "\ufeff\u2060", "Untitled"],
)
async def test_a_blank_title_is_refused_like_none(untitled_workspace, title):
    await _set_title(untitled_workspace, title)
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    _only_problem(raised.value.content)
    assert await _latest(form_id) is None


async def test_publish_works_once_the_workspace_has_a_title(untitled_workspace):
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException):
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    await _set_title(untitled_workspace, "Acme")
    published = await container.workspace_form_service().publish_form(
        untitled_workspace.id, form_id, testUser
    )
    assert published.version == 1


async def test_a_new_form_is_created_under_the_title_rule(untitled_workspace):
    form_id = await _draft(untitled_workspace)
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=untitled_workspace.id, query=str(form_id)
        )
    )
    assert workspace_form.settings.publish_checks_version == PUBLISH_CHECKS_VERSION
    assert requires_workspace_title(workspace_form.settings.publish_checks_version)


@pytest.mark.parametrize("version", [None, 1])
async def test_an_existing_form_publishes_and_republishes_in_an_untitled_workspace(
    untitled_workspace, version
):
    form_id = await _draft(untitled_workspace)
    await _set_checks_version(untitled_workspace, form_id, version)
    assert (await _publish(untitled_workspace, form_id)).version == 1
    # a republish is a new publish of an edited draft
    await _rename_draft(form_id, "Second")
    assert (await _publish(untitled_workspace, form_id)).version == 2
    # a blank title is no different from none for an older form
    await _set_title(untitled_workspace, " \u200b ")
    await _rename_draft(form_id, "Third")
    assert (await _publish(untitled_workspace, form_id)).version == 3


async def test_an_older_form_keeps_why_we_ask_as_it_was(untitled_workspace):
    """The version bump changes no other check: a form from before the
    checks publishes without a reason, one from version 1 still needs it."""
    before = await _draft(untitled_workspace, T.EMAIL)
    await _set_checks_version(untitled_workspace, before, None)
    assert (await _publish(untitled_workspace, before)).version == 1

    first = await _draft(untitled_workspace, T.EMAIL)
    await _set_checks_version(untitled_workspace, first, 1)
    with pytest.raises(HTTPException) as raised:
        await _publish(untitled_workspace, first)
    codes = [p["code"] for p in raised.value.content["problems"]]
    assert codes == [MISSING_WHY_WE_ASK]


async def test_a_new_form_in_a_titled_workspace_is_not_affected(workspace):
    form_id = await _draft(workspace)
    assert (await _publish(workspace, form_id)).version == 1


async def test_the_older_form_check_does_not_read_the_workspace(
    untitled_workspace, monkeypatch
):
    """An older form is not held to the rule, so publishing it makes no
    workspace lookup for it."""
    form_id = await _draft(untitled_workspace)
    await _set_checks_version(untitled_workspace, form_id, 1)

    async def boom(self, workspace_id):
        raise AssertionError("the workspace title was read")

    monkeypatch.setattr(
        type(container.workspace_form_service()), "_workspace_title", boom
    )
    assert (await _publish(untitled_workspace, form_id)).version == 1


async def test_the_handle_does_not_stand_in_for_a_title(untitled_workspace):
    """The default workspace's handle is its owner's id; even a readable
    handle is no title: respondents should see a real name."""
    await container.workspace_repo().set_fields(
        untitled_workspace, {"workspace_name": "acme-forms"}
    )
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    _only_problem(raised.value.content)


async def test_a_workspace_that_is_not_a_personal_one_is_checked_too(workspace_pro):
    """A titled additional workspace publishes; the same one untitled does not."""
    from tests.app.controllers.data import proUser

    form = await container.workspace_form_service().create_form(
        workspace_pro.id, _form(), proUser
    )
    published = await container.workspace_form_service().publish_form(
        workspace_pro.id, form.form_id, proUser
    )
    assert published.version == 1
    await _set_title(workspace_pro, " ")
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace_pro.id, form.form_id, proUser
        )
    _only_problem(raised.value.content)


async def test_it_comes_with_the_other_publish_problems(untitled_workspace):
    form_id = await _draft(untitled_workspace, T.EMAIL)  # no "why we ask"
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    codes = [p["code"] for p in raised.value.content["problems"]]
    assert codes == [WORKSPACE_TITLE_MISSING, MISSING_WHY_WE_ASK]


async def test_the_refusal_shows_no_other_workspace_data(untitled_workspace):
    await container.workspace_repo().set_fields(
        untitled_workspace, {"workspace_name": "acme-handle", "description": "SECRET"}
    )
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            untitled_workspace.id, form_id, testUser
        )
    text = json.dumps(raised.value.content)
    for private in (
        str(untitled_workspace.id),
        str(untitled_workspace.owner_id),
        "acme-handle",
        "SECRET",
    ):
        assert private not in text
    assert set(raised.value.content) == {"code", "message", "problems"}
    assert set(raised.value.content["problems"][0]) == {"code", "fieldId", "message"}


# -------------------------------------------------- what the check leaves be


async def test_a_form_that_is_already_live_stays_live(workspace):
    form_id = await _draft(workspace)
    published = await container.workspace_form_service().publish_form(
        workspace.id, form_id, testUser
    )
    assert published.version == 1
    await _set_title(workspace, "")
    # still served as it was published: nothing is withdrawn
    live = await _latest(form_id)
    assert live is not None and live.version == 1
    # a republish is a new publish, and is checked
    with pytest.raises(HTTPException) as raised:
        await container.workspace_form_service().publish_form(
            workspace.id, form_id, testUser
        )
    _only_problem(raised.value.content)
    assert (await _latest(form_id)).version == 1


async def test_drafting_and_saving_need_no_title(untitled_workspace):
    form_id = await _draft(untitled_workspace)
    draft = await container.form_service().get_form_document_by_id(form_id)
    draft.title = "Renamed"
    await container.form_service().update_form(form_id=form_id, form=draft)
    assert (
        await container.form_service().get_form_document_by_id(form_id)
    ).title == "Renamed"


async def test_a_template_needs_no_title(untitled_workspace):
    """Templates are not shown to respondents as a form: nobody receives
    answers through one, so only publishing is checked."""
    form_id = await _draft(untitled_workspace)
    template = await container.workspace_form_service().duplicate_form(
        untitled_workspace.id, form_id, testUser, is_template=True
    )
    assert template is not None


# ------------------------------------------------------ every way to publish


async def test_the_builder_endpoint_refuses_then_publishes(
    client: AsyncClient, untitled_workspace, test_user_cookies
):
    form_id = await _draft(untitled_workspace)
    path = f"/api/v1/workspaces/{untitled_workspace.id}/forms/{form_id}/publish"
    response = await client.post(path, cookies=test_user_cookies)
    assert response.status_code == 422
    assert _only_problem(response.json())["fieldId"] is None
    assert await _latest(form_id) is None

    await _set_title(untitled_workspace, "Acme")
    assert (await client.post(path, cookies=test_user_cookies)).status_code == 200


async def test_the_public_api_refuses_then_publishes(
    client: AsyncClient, untitled_workspace
):
    token = await _token(untitled_workspace.id)
    form_id = (await _create(client, token)).json()["formId"]
    path = f"{BASE}/forms/{form_id}/publish"
    response = await client.post(path, headers=_auth(token))
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == FORM_NOT_PUBLISHABLE
    assert "no title" in body["message"]
    assert await _latest(form_id) is None

    await _set_title(untitled_workspace, "Acme")
    assert (await client.post(path, headers=_auth(token))).status_code == 200


async def test_the_mcp_server_refuses_then_publishes(
    client: AsyncClient, untitled_workspace
):
    form_id = await _draft(untitled_workspace)
    token = await _make_key(untitled_workspace.id, ["forms:write"])
    result = await _call_tool(client, token, "publish_form", {"form_id": str(form_id)})
    # the MCP server's error text for a refused publish is empty by contract
    # (test_mcp_contract: "errors read as before"); what matters here is that
    # it is an error and nothing went live
    assert result.get("isError") is True, result
    assert await _latest(form_id) is None

    await _set_title(untitled_workspace, "Acme")
    result = await _call_tool(client, token, "publish_form", {"form_id": str(form_id)})
    assert not result.get("isError"), result


async def test_the_spec_writer_refuses(untitled_workspace):
    form_id = await _draft(untitled_workspace)
    with pytest.raises(HTTPException) as raised:
        await container.form_spec_writer().publish(
            untitled_workspace.id, form_id, testUser
        )
    _only_problem(raised.value.content)
    assert await _latest(form_id) is None
