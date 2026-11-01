"""The options another form's answers give, and the privacy rules around them:
who may point at them, which responses count, what a respondent can see, that a
new, deleted, edited or withdrawn response changes them at once, and the caps."""

import datetime as dt

import pytest
from common.clock import utcnow
from common.ids import RecordId
from common.models.user import User
from sqlalchemy import update

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.option_sources import text
from backend.app.services.option_sources.checks import FORBIDDEN_CODE, INVALID_CODE
from backend.app.services.option_sources.service import GONE
from tests.app.controllers.data import testUser, testUser1
from tests.app.option_sources.helpers import make_list, publish, question, submit
from tests.app.option_sources.helpers import choice, choices
from tests.app.option_sources.helpers import text as text_answer

pytestmark = pytest.mark.asyncio


def sources():
    return container.option_source_service()


def listed(options):
    return [o.label for o in options.options]


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return (
        error.content["code"] if isinstance(error.content, dict) else str(error.content)
    )


ROLE_CHOICES = [
    {"id": "r1", "value": "Speaker"},
    {"id": "r2", "value": "Guest"},
    {"id": "r3", "value": "Volunteer"},
]


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


@pytest.fixture()
async def registered(workspace):
    """A published form of participants: a name, a role and an email."""
    return await publish(
        workspace,
        [
            question("name", "short_text", "Name"),
            question("role", "dropdown", "Role", choices=ROLE_CHOICES),
            question(
                "roles",
                "multiple_choice",
                "Roles",
                choices=ROLE_CHOICES,
                allow_multiple_selection=True,
            ),
            question("mail", "email", "Email", why_we_ask="To reply to you"),
        ],
        title="Participants",
    )


def source_of(form, question_id="name"):
    return {"kind": "form_answers", "form_id": form.form_id, "question_id": question_id}


async def register(workspace, form, name, role=None, user=None, **kwargs):
    answers = {"name": text_answer(name)}
    if role:
        answers["role"] = choice(role)
    return await submit(workspace, form, answers, user=user, **kwargs)


async def options_of(workspace, form, question_id="name"):
    return await sources().options(workspace.id, source_of(form, question_id))


# ------------------------------------------------------------------ the options


async def test_labels_are_deduplicated_sorted_and_given_keyed_ids(
    workspace, registered
):
    for name in (
        "  zoë  Dam ",
        "Zoë dam",
        "Bob",
        "alice",
        "Bob",
        "",
        "x" * 201,
        "bad​name",
    ):
        await register(workspace, registered, name)
    built = await options_of(workspace, registered)
    # first spelling kept (the oldest response), compared folded, in alphabetical order
    assert listed(built) == ["alice", "Bob", "zoë Dam"]
    assert built.available and not built.truncated and built.responses == 8
    assert all(o.id.startswith("fa") and len(o.id) == 24 for o in built.options)
    # an id says nothing of the label, and is the same on every rebuild
    assert not any(o.label.lower() in o.id for o in built.options)
    again = await options_of(workspace, registered)
    assert [o.id for o in again.options] == [o.id for o in built.options]


async def test_a_dropdown_or_multiple_choice_gives_the_texts_of_the_chosen_options(
    workspace, registered
):
    await submit(
        workspace,
        registered,
        {"name": text_answer("A"), "role": choice("r2"), "roles": choices("r1", "r3")},
    )
    await submit(
        workspace, registered, {"name": text_answer("B"), "role": choice("r2")}
    )
    assert listed(await options_of(workspace, registered, "role")) == ["Guest"]
    assert listed(await options_of(workspace, registered, "roles")) == [
        "Speaker",
        "Volunteer",
    ]


async def test_a_new_response_a_deletion_and_a_deletion_request_change_the_options_at_once(
    workspace, registered
):
    first = await register(workspace, registered, "Alice")
    assert listed(await options_of(workspace, registered)) == ["Alice"]
    second = await register(workspace, registered, "Bob")
    assert listed(await options_of(workspace, registered)) == ["Alice", "Bob"]
    # a respondent asks for deletion (any status): the label leaves the options
    repo = container.form_response_repo()
    await repo.add_deletion_request(
        await repo.get_response(second.response_id), second.response_id
    )
    assert listed(await options_of(workspace, registered)) == ["Alice"]
    # the response is deleted
    await container.form_response_service().delete_form_responses(registered.form_id)
    assert listed(await options_of(workspace, registered)) == []
    assert first.response_id != second.response_id


async def test_a_declined_or_completed_request_also_removes_the_label(
    workspace, registered
):
    done = await register(workspace, registered, "Done")
    declined = await register(workspace, registered, "Declined")
    await register(workspace, registered, "Kept")
    repo = container.form_response_repo()
    from backend.db.models import ResponseDeletionRequestRow

    table = ResponseDeletionRequestRow.__table__
    for response, status in ((done, "success"), (declined, "declined")):
        request = await repo.add_deletion_request(
            await repo.get_response(response.response_id), response.response_id
        )
        async with repo._session() as session, session.begin():
            await session.execute(
                update(table)
                .where(table.c.id == str(request.id))
                .values(doc=table.c.doc.op("||")({"status": status}))
            )
    # a request closed as declined keeps the response, and it is still not shown here
    assert listed(await options_of(workspace, registered)) == ["Kept"]


async def test_an_anonymous_submission_never_becomes_an_option_but_a_public_one_does(
    workspace, registered
):
    await register(workspace, registered, "Public visitor")  # not signed in
    await register(workspace, registered, "Signed in", user=testUser1)
    from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel

    await container.workspace_form_service().submit_response(
        workspace.id,
        registered.form_id,
        StandardFormResponseCamelModel(
            answers={"name": text_answer("Anonymous by choice")}, anonymize=True
        ),
        testUser1,
    )
    assert listed(await options_of(workspace, registered)) == [
        "Public visitor",
        "Signed in",
    ]


async def test_an_expired_response_is_not_offered(workspace, registered):
    old = await register(workspace, registered, "Expired")
    await register(workspace, registered, "Current")
    repo = container.form_response_repo()
    table = repo.row.__table__
    past = (utcnow() - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    async with repo._session() as session, session.begin():
        await session.execute(
            update(table)
            .where(table.c.response_id == old.response_id)
            .values(doc=table.c.doc.op("||")({"expiration": past}))
        )
    assert listed(await options_of(workspace, registered)) == ["Current"]


async def test_an_edited_response_changes_its_option(workspace, registered):
    response = await register(workspace, registered, "Before")
    assert listed(await options_of(workspace, registered)) == ["Before"]
    repo = container.form_response_repo()
    stored = await repo.get_response(response.response_id)
    import json
    from common.services.crypto_service import crypto_service

    stored.answers = crypto_service.encrypt(
        workspace_id=workspace.id,
        form_id=registered.form_id,
        data=json.dumps({"name": {"type": "text", "text": "After"}}),
    )
    await repo.save(stored)
    assert listed(await options_of(workspace, registered)) == ["After"]


async def test_the_options_are_cut_at_the_caps_and_say_so(
    workspace, registered, monkeypatch
):
    monkeypatch.setattr(text, "ANSWER_OPTIONS_MAX", 3)
    for name in ("a", "b", "c", "d", "e"):
        await register(workspace, registered, name)
    cut = await options_of(workspace, registered)
    assert len(cut.options) == 3 and cut.truncated
    monkeypatch.setattr(text, "ANSWER_OPTIONS_MAX", 1000)
    monkeypatch.setattr(text, "ANSWER_RESPONSES_MAX", 500)
    sources()._cache.clear()
    from backend.app.services.option_sources import service as module

    monkeypatch.setattr(module, "BATCH", 2)
    capped = await options_of(workspace, registered)
    # fewer responses than the cap: not cut
    assert not capped.truncated and len(capped.options) == 5
    monkeypatch.setattr(text, "ANSWER_RESPONSES_MAX", 4)
    sources()._cache.clear()
    capped = await options_of(workspace, registered)
    assert capped.truncated and len(capped.options) == 4


async def test_a_source_that_is_gone_offers_nothing(workspace, registered):
    await register(workspace, registered, "Alice")
    missing = await sources().options(
        workspace.id,
        {"kind": "form_answers", "form_id": registered.form_id, "question_id": "nope"},
    )
    assert missing.available is False and missing.options == ()
    no_form = await sources().options(
        workspace.id,
        {"kind": "form_answers", "form_id": str(RecordId()), "question_id": "name"},
    )
    assert no_form.available is False
    assert (
        await sources().options(
            workspace.id, {"kind": "list", "list_id": str(RecordId())}
        )
    ).available is False
    assert (
        await sources().options(workspace.id, {"kind": "url", "url": "http://x"})
    ) is GONE


async def test_another_workspaces_form_gives_nothing(
    workspace, workspace_1, registered
):
    await register(workspace, registered, "Alice")
    built = await sources().options(workspace_1.id, source_of(registered))
    assert built.available is False and built.options == ()


async def test_a_list_is_served_in_its_order_and_a_change_shows_at_once(workspace):
    created = await make_list(
        workspace, items=[("b", None), ("A", None), ("c", "g")], order="alphabetical"
    )
    source = {"kind": "list", "list_id": created.id}
    assert listed(await sources().options(workspace.id, source)) == ["A", "b", "c"]
    from backend.app.services.option_lists.service import ItemDto, OptionListUpdateDto

    await container.option_list_service().update_list(
        workspace.id,
        created.id,
        OptionListUpdateDto(
            order="manual", items=[ItemDto(label="z"), ItemDto(label="y")]
        ),
        testUser,
    )
    assert listed(await sources().options(workspace.id, source)) == ["z", "y"]
    # another process wrote it (no ``forget`` here): the revision still shows the change
    sources()._cache.clear()
    assert listed(await sources().options(workspace.id, source)) == ["z", "y"]


# ----------------------------------------------------------- who may point at it


@pytest.fixture()
async def privacy_officer(workspace):
    user = User(id=str(RecordId()), sub="privacy@sources.example")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=user.id,
            roles=[WorkspaceRoles.PRIVACY_OFFICER],
        )
    )
    return user


@pytest.fixture()
async def editor(workspace):
    user = User(id=str(RecordId()), sub="editor@sources.example")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=user.id, roles=[WorkspaceRoles.EDITOR]
        )
    )
    return user


async def test_a_creator_needs_response_read_on_the_source_form(
    workspace, registered, privacy_officer, editor
):
    await sources().authorize_source(workspace.id, source_of(registered), testUser)
    await sources().authorize_source(workspace.id, source_of(registered), editor)
    error = await refused(
        sources().authorize_source(workspace.id, source_of(registered), privacy_officer)
    )
    assert error.status_code == 403 and code_of(error) == FORBIDDEN_CODE
    stranger = await refused(
        sources().authorize_source(workspace.id, source_of(registered), testUser1)
    )
    assert stranger.status_code == 403


async def test_an_api_key_never_points_a_form_at_another_forms_answers(
    workspace, registered
):
    key_user = testUser.model_copy(update={"auth_method": "api_key"})
    error = await refused(
        sources().authorize_source(workspace.id, source_of(registered), key_user)
    )
    assert error.status_code == 403 and code_of(error) == FORBIDDEN_CODE
    # a list is another matter
    created = await make_list(workspace)
    await sources().authorize_source(
        workspace.id, {"kind": "list", "list_id": created.id}, key_user
    )


async def test_the_source_must_be_a_usable_question_of_another_form_of_this_workspace(
    workspace, workspace_1, registered
):
    own = await publish(
        workspace, [question("name", "short_text", "Name")], title="Own"
    )
    other = await publish(
        workspace_1,
        [question("name", "short_text", "Name")],
        user=testUser1,
        title="Theirs",
    )
    internal = await publish(
        workspace,
        [
            question("hidden_q", "short_text", "Staff note"),
            question("name", "short_text", "N"),
        ],
        title="Internal",
    )
    sourced = await publish(
        workspace,
        [
            question(
                "c",
                "dropdown",
                "C",
                source={"kind": "list", "list_id": (await make_list(workspace)).id},
            )
        ],
        title="Sourced",
    )
    cases = [
        (source_of(own), own.form_id, "its own answers"),
        (source_of(other), None, "not in this workspace"),
        ({**source_of(registered), "question_id": "mail"}, None, "an email question"),
        ({**source_of(registered), "question_id": "missing"}, None, "no such question"),
        (source_of(sourced, "c"), None, "a sourced question"),
        ({"kind": "list", "list_id": str(RecordId())}, None, "no such list"),
    ]
    for source, own_form, why in cases:
        error = await refused(
            sources().authorize_source(workspace.id, source, testUser, own_form)
        )
        assert error.status_code == 422 and code_of(error) == INVALID_CODE, why
    assert internal.form_id  # (a staff-only question is checked in the builder tests)


async def test_a_list_of_another_workspace_cannot_be_used(workspace, workspace_1):
    theirs = await make_list(workspace_1, user=testUser1)
    error = await refused(
        sources().authorize_source(
            workspace.id, {"kind": "list", "list_id": theirs.id}, testUser
        )
    )
    assert code_of(error) == INVALID_CODE
