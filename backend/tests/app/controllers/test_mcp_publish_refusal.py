"""The MCP ``publish_form`` tool says why a publish was refused.

A 422 ``form_not_publishable`` comes back as the tool's error text, one
problem per line as ``code: message`` (``code (field <id>): message`` for a
problem that belongs to a question), in the server's order. Only the code, the
question id and the message of each problem: no report id, no other part of
the refusal. Every other refusal is answered as before (empty error text), and
a key's scope and workspace are checked first, as before.
"""

import json
from http import HTTPStatus

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardFieldValidations,
    StandardForm,
    StandardFormField,
    StandardFormFieldType as T,
)

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.mcp.server import (
    MAX_PUBLISH_PROBLEM_CHARS,
    MAX_PUBLISH_PROBLEMS,
    _publish_refusal_text,
)
from backend.app.services.publish_checks import (
    FORM_NOT_PUBLISHABLE,
    MISSING_WHY_WE_ASK,
    NEEDS_REVIEW,
    PRESET_ANSWER,
    REQUIRED_UNANSWERABLE,
    WORKSPACE_TITLE_MISSING,
    ensure_publishable,
    review_problem,
    workspace_title_problem,
)
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_mcp_server import _call_tool, _make_key

HEADER = "This form can't be published yet:"
PREFIX = "Error executing tool publish_form: "


def _refusal(problems) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": FORM_NOT_PUBLISHABLE,
            "message": "This form can't be published yet: " + "irrelevant",
            "problems": problems,
        },
    )


def _problem(code="code", field_id=None, message="Message.", **extra) -> dict:
    return {"code": code, "fieldId": field_id, "message": message, **extra}


def _question(field_id, title, field_type=T.SHORT_TEXT, required=False, **props):
    return StandardFormField(
        id=field_id,
        type=field_type,
        title=title,
        validations=StandardFieldValidations(required=required),
        properties=StandardFieldProperty(fields=[], **props),
    )


def _form(*questions) -> StandardForm:
    return StandardForm(
        title="Sign-up",
        fields=[
            StandardFormField(
                id="page-1",
                type=T.SLIDE,
                properties=StandardFieldProperty(fields=list(questions)),
            )
        ],
    )


async def _draft(workspace, form: StandardForm, user=testUser) -> str:
    created = await container.workspace_form_service().create_form(
        workspace.id, form, user
    )
    return str(created.form_id)


# ------------------------------------------------------ the text, as a unit


class TestRefusalText:
    def test_each_problem_is_a_line_of_code_and_message(self):
        text = _publish_refusal_text(
            _refusal(
                [
                    _problem("needs_review", None, "Review it."),
                    _problem("missing_why_we_ask", "q1", "Add a reason."),
                ]
            )
        )
        assert text == (
            f"{HEADER}\n"
            "needs_review: Review it.\n"
            "missing_why_we_ask (field q1): Add a reason."
        )

    def test_the_servers_order_is_kept(self):
        problems = [_problem(f"c{n}", f"f{n}", f"m{n}") for n in (3, 1, 2)]
        lines = _publish_refusal_text(_refusal(problems)).splitlines()[1:]
        assert [line.split(" ")[0] for line in lines] == ["c3", "c1", "c2"]

    def test_needs_review_names_no_report(self):
        problem = review_problem("65f0000000000000000000aa")
        text = _publish_refusal_text(_refusal([problem]))
        assert text == f"{HEADER}\n{NEEDS_REVIEW}: {problem['message']}"
        assert "65f0000000000000000000aa" not in text
        assert "importId" not in text

    def test_workspace_title_missing(self):
        problem = workspace_title_problem("")
        text = _publish_refusal_text(_refusal([problem]))
        assert text == f"{HEADER}\n{WORKSPACE_TITLE_MISSING}: {problem['message']}"

    def test_the_problems_of_the_checks_read_as_they_are_made(self):
        form = _form(
            _question("q1", "Your email", T.EMAIL),
            _question("q2", "Pick one", T.DROPDOWN, required=True),
        )
        with pytest.raises(HTTPException) as raised:
            ensure_publishable(
                form,
                checks_version=2,
                review=review_problem("report-1"),
                workspace_problem=workspace_title_problem(None),
            )
        problems = raised.value.content["problems"]
        lines = _publish_refusal_text(raised.value).splitlines()
        assert lines[0] == HEADER
        assert [line.split(":")[0] for line in lines[1:]] == [
            NEEDS_REVIEW,
            WORKSPACE_TITLE_MISSING,
            f"{MISSING_WHY_WE_ASK} (field q1)",
            f"{REQUIRED_UNANSWERABLE} (field q2)",
        ]
        for problem, line in zip(problems, lines[1:]):
            assert line.endswith(": " + problem["message"])

    def test_a_preset_answer_problem(self):
        question = _question(
            "q1",
            "Pick one",
            T.MULTIPLE_CHOICE,
            choices=[{"id": "a", "value": "A"}, {"id": "b", "value": "B"}],
        )
        question.value = "A"
        with pytest.raises(HTTPException) as raised:
            ensure_publishable(_form(question))
        lines = _publish_refusal_text(raised.value).splitlines()
        assert lines[1].startswith(f"{PRESET_ANSWER} (field q1): ")

    def test_a_message_stays_on_one_line_and_is_capped(self):
        text = _publish_refusal_text(
            _refusal(
                [
                    _problem(message="a\nb\r\n  c\td"),
                    _problem(message="x" * 5000),
                ]
            )
        )
        first, second = text.splitlines()[1:]
        assert first == "code: a b c d"
        assert len(second) == MAX_PUBLISH_PROBLEM_CHARS
        assert second.endswith("...")

    def test_only_the_first_problems_are_listed_then_how_many_more(self):
        problems = [
            _problem(f"c{n}", f"f{n}", f"m{n}")
            for n in range(MAX_PUBLISH_PROBLEMS + 7)
        ]
        lines = _publish_refusal_text(_refusal(problems)).splitlines()
        assert len(lines) == 1 + MAX_PUBLISH_PROBLEMS + 1
        assert lines[1] == "c0 (field f0): m0"
        assert lines[MAX_PUBLISH_PROBLEMS] == (
            f"c{MAX_PUBLISH_PROBLEMS - 1} "
            f"(field f{MAX_PUBLISH_PROBLEMS - 1}): m{MAX_PUBLISH_PROBLEMS - 1}"
        )
        assert lines[-1] == "and 7 more"

    def test_exactly_the_cap_has_no_more_line(self):
        problems = [_problem(f"c{n}") for n in range(MAX_PUBLISH_PROBLEMS)]
        lines = _publish_refusal_text(_refusal(problems)).splitlines()
        assert len(lines) == 1 + MAX_PUBLISH_PROBLEMS
        assert "more" not in lines[-1]

    def test_nothing_but_code_field_and_message_is_passed_on(self):
        text = _publish_refusal_text(
            _refusal(
                [
                    _problem(
                        "c",
                        "f1",
                        "Fix it.",
                        importId="import-secret",
                        report={"rows": ["answer-secret"]},
                        email="a@example.org",
                    )
                ]
            )
        )
        text += _publish_refusal_text(
            HTTPException(
                status_code=422,
                content={
                    "code": FORM_NOT_PUBLISHABLE,
                    "message": "top-level-secret",
                    "workspace": "workspace-secret",
                    "problems": [_problem("c", None, "Fix it.")],
                },
            )
        )
        for secret in (
            "import-secret",
            "answer-secret",
            "a@example.org",
            "top-level-secret",
            "workspace-secret",
        ):
            assert secret not in text

    @pytest.mark.parametrize(
        "status, content",
        [
            (403, "Forbidden"),
            (404, {"message": "Not found"}),
            (410, {"message": "Gone"}),
            (409, {"message": "Not now"}),
            (422, {"code": "something_else", "problems": [_problem()]}),
            (422, "a plain message"),
            (422, {"code": FORM_NOT_PUBLISHABLE}),
        ],
    )
    def test_other_refusals_have_no_reasons_text(self, status, content):
        error = HTTPException(status_code=status, content=content)
        if isinstance(content, dict) and content.get("code") == FORM_NOT_PUBLISHABLE:
            # a refusal without problems still reads as a refusal, not a crash
            assert _publish_refusal_text(error) == HEADER
        else:
            assert _publish_refusal_text(error) is None


# ------------------------------------------------ through the real transport


class TestOverTheTransport:
    async def test_a_form_with_problems_says_which(
        self, client: AsyncClient, workspace
    ):
        form_id = await _draft(
            workspace,
            _form(
                _question("q-email", "Your email", T.EMAIL),
                _question("q-pick", "Pick one", T.DROPDOWN, required=True),
            ),
        )
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result["isError"] is True
        assert result["content"][0]["type"] == "text"
        text = result["content"][0]["text"]
        assert text.startswith(PREFIX + HEADER + "\n")
        lines = text[len(PREFIX) :].splitlines()
        assert [line.split(":")[0] for line in lines[1:]] == [
            f"{MISSING_WHY_WE_ASK} (field q-email)",
            f"{REQUIRED_UNANSWERABLE} (field q-pick)",
        ]
        assert '"Your email" asks for personal details' in lines[1]
        assert '"Pick one" is required' in lines[2]
        # nothing went live
        assert await container.form_repo().get_latest_version_of_form(form_id) is None

    async def test_an_untitled_workspace_says_so(self, client: AsyncClient, workspace):
        await container.workspace_repo().set_fields(workspace, {"title": ""})
        form_id = await _draft(workspace, _form(_question("q", "Your name")))
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert text.startswith(f"{PREFIX}{HEADER}\n{WORKSPACE_TITLE_MISSING}: ")
        assert "Your workspace has no title yet" in text
        assert len(text.splitlines()) == 2

    async def test_a_form_that_needs_review_says_so_without_the_report(
        self, client: AsyncClient, workspace
    ):
        form_id = await _draft(workspace, _form(_question("q", "Your name")))
        repo = container.workspace_form_repo()
        workspace_form = await repo.get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=form_id
        )
        workspace_form.settings.needs_review = True
        workspace_form.settings.import_id = "report-id-123"
        await repo.save(workspace_form)
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert text.startswith(f"{PREFIX}{HEADER}\n{NEEDS_REVIEW}: ")
        assert "report-id-123" not in text
        assert len(text.splitlines()) == 2

    async def test_the_refusal_is_text_only(
        self, client: AsyncClient, workspace
    ):
        form_id = await _draft(
            workspace, _form(_question("q-email", "Your email", T.EMAIL))
        )
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert set(result) == {"content", "isError"}
        assert json.dumps(result).count("q-email") == 1

    async def test_a_publishable_form_is_unchanged(
        self, client: AsyncClient, workspace
    ):
        form_id = await _draft(workspace, _form(_question("q", "Your name")))
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result["isError"] is False
        assert json.loads(result["content"][0]["text"])["published"] is True


class TestPermissionsUnchanged:
    @pytest.mark.parametrize("status", [403, 404, 410])
    async def test_other_refusals_answer_as_before(
        self, client: AsyncClient, workspace, monkeypatch, status
    ):
        form_id = await _draft(workspace, _form(_question("q", "Your name")))

        async def refuse(*args, **kwargs):
            raise HTTPException(status_code=status, content={"message": "Secret."})

        monkeypatch.setattr(container.workspace_form_service(), "publish_form", refuse)
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result == {
            "content": [{"type": "text", "text": PREFIX}],
            "isError": True,
        }

    async def test_a_key_without_write_scope_is_refused_before_any_check(
        self, client: AsyncClient, workspace
    ):
        # a form that would be refused with reasons, were the key allowed
        form_id = await _draft(
            workspace, _form(_question("q-email", "Your email", T.EMAIL))
        )
        token = await _make_key(workspace.id, ["forms:read"])
        result = await _call_tool(client, token, "publish_form", {"form_id": form_id})
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "forms:write" in text
        assert MISSING_WHY_WE_ASK not in text
        assert "q-email" not in text

    async def test_a_form_of_another_workspace_is_not_found_not_checked(
        self, client: AsyncClient, workspace, workspace_1
    ):
        other = await _draft(
            workspace_1,
            _form(_question("q-email", "Your email", T.EMAIL)),
            testUser1,
        )
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(client, token, "publish_form", {"form_id": other})
        assert result["isError"] is True
        text = result["content"][0]["text"]
        assert "does not exist in this workspace" in text
        assert MISSING_WHY_WE_ASK not in text
        assert "q-email" not in text
