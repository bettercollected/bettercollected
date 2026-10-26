"""The responses group's repositories (form responses and their deletion
requests, workspace responders and tags, responder groups), Postgres only
since 4.1.

These steps ran against the 4.0 Mongo repositories too while both stores
existed (the parity tests of the dual run). The results they agreed on are
pinned in ``tests/fixtures/responses_repositories.json`` (ids and timestamps
aside, as the parity harness compared them); a few are spelled out below as
well. The forms-group data the repository composes over (a form's title, the
workspace that imported it) is read through the forms repositories, as the
application does.

The fixture is written from a run of the 4.0-era repositories whose parity
tests passed (``BC_PIN_RESPONSES_REPOSITORIES=1``, one process), never
regenerated to make a change pass. Skipped unless DATABASE_URL points at a
*_test database.
"""

import datetime as dt
from pathlib import Path

from backend.app.container import container
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.response_scope import ResponseScope
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDocument,
)
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from common.records import RecordId
from tests.app.repositories.parity import sessions, strip  # noqa: F401
from tests.app.repositories.pinned import Pinned

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
FIXTURE = Path(__file__).parents[2] / "fixtures" / "responses_repositories.json"
PIN_ENV = "BC_PIN_RESPONSES_REPOSITORIES"


def pinned(case: str) -> Pinned:
    return Pinned(FIXTURE, PIN_ENV, case)


def oid(n: int) -> RecordId:
    """A fixed id: the pinned results name workspaces, users and tags."""
    return RecordId(f"{n:024x}")


def at(minutes):
    return T0 + dt.timedelta(minutes=minutes)


def legacy(workspace_id, *form_ids):
    """A scope whose forms are linked to this workspace only: responses
    stored before #768 (no workspace_id, as seeded here) are its own."""
    return ResponseScope(workspace_id, tuple(form_ids), tuple(form_ids))


def response(form_id, response_id, minutes, **extra):
    return FormResponseDocument(
        id=RecordId(),
        form_id=form_id,
        response_id=response_id,
        created_at=at(minutes),
        **extra,
    )


def responses_repo(sessions):
    return PostgresFormResponseRepository(
        sessions, container.form_repo(), container.workspace_form_repo()
    )


async def seed(repo, *documents):
    for document in documents:
        await repo.save(document)


async def link_form(workspace, form_id, title, importer):
    await container.form_repo().save_form(FormDocument(form_id=form_id, title=title))
    await container.workspace_form_repo().save(
        WorkspaceFormDocument(
            workspace_id=workspace, form_id=form_id, user_id=importer
        )
    )


# ------------------------------------------------------------------ responses
async def test_responses_with_the_ai_notice(sessions):
    """#752: only responses submitted here whose page showed the notice for
    this provider name since the setting was turned on."""
    postgres = responses_repo(sessions)
    case = pinned("responses_with_the_ai_notice")

    def shown(minutes, name="OpenAI", provider="self"):
        return dict(
            answers={},
            provider=provider,
            ai_notice_shown_at=at(minutes),
            ai_notice_provider_name=name,
        )

    await seed(
        postgres,
        response("n1", "a1", 10, **shown(9)),
        response("n1", "a2", 20, **shown(19)),
        response("n1", "a3", 30, **shown(29, name="Google Gemini")),
        response("n1", "a4", 40, answers={}, provider="self"),  # never saw it
        response("n1", "a5", 50, **shown(2)),  # shown before the setting
        response("n1", "a6", 60, **shown(59, provider="google")),  # imported
        response("n2", "a7", 70, **shown(69)),  # another form
    )
    ws = oid(1)
    n1, n3 = legacy(ws, "n1"), legacy(ws, "n3")
    await case.steps(
        postgres,
        [
            ("list_recent_with_ai_notice", lambda: (n1, "OpenAI", at(5), 10)),
            ("list_recent_with_ai_notice", lambda: (n1, "OpenAI", at(5), 1)),
            ("list_recent_with_ai_notice", lambda: (n1, "Google Gemini", at(5), 10)),
            ("count_with_ai_notice", lambda: (n1, "OpenAI", at(5))),
            ("count_with_ai_notice", lambda: (n1, "OpenAI", at(0))),
            ("count_with_ai_notice", lambda: (n3, "OpenAI", at(0))),
        ],
    )
    listed = await postgres.list_recent_with_ai_notice(n1, "OpenAI", at(5), 10)
    assert [r.response_id for r in listed] == ["a2", "a1"]
    assert await postgres.count_with_ai_notice(n1, "OpenAI", at(0)) == 3
    case.check()


async def test_response_listings_compose_over_forms(sessions):
    ws = oid(1)
    # forms-group data: the repository composes over it
    for form_id, title in (("f1", "Alpha"), ("f2", "Beta")):
        await link_form(ws, form_id, title, "importer")
    postgres = responses_repo(sessions)
    case = pinned("response_listings_compose_over_forms")
    await seed(
        postgres,
        response("f1", "r1", 1, answers={}, dataOwnerIdentifier="a@example.com"),
        response("f1", "r2", 2, answers={}, dataOwnerIdentifier="b@example.com"),
        response("f2", "r3", 3, answers={}, dataOwnerIdentifier="a@example.com"),
        response("f1", "r4", 4),  # no answers: a deletion-only stub, not listed
        response("orphan", "r5", 5, answers={}),  # its form is gone: dropped
    )
    for response_id in ("r1", "r3"):
        await postgres.add_deletion_request(
            await postgres.get_response(response_id), response_id
        )

    ids = legacy(ws, "f1", "f2", "orphan", "missing")
    f1, f2 = legacy(ws, "f1"), legacy(ws, "f2")
    user_a = User(id=str(oid(2)), sub="a@example.com")
    await case.page("all responses", lambda: postgres.get_form_responses(ids))
    page = await case.page(
        "responses of a",
        lambda: postgres.get_form_responses(ids, data_owner_identifier="a@example.com"),
    )
    assert {i["response_id"] for i in page.items} == {"r1", "r3"}
    assert (
        next(i for i in page.items if i["response_id"] == "r3")["status"] == "pending"
    )
    assert (
        next(i for i in page.items if i["response_id"] == "r1")["form_title"] == "Alpha"
    )
    # a filter value is literal text, ignoring case: regex characters match
    # themselves and a bad pattern is no error
    for value, expected in (
        ("B@EX", {"r2"}),
        ("^b@", set()),
        ("(", set()),
        ("a.example", set()),
    ):
        page = await case.page(
            f"filter {value}",
            lambda: postgres.get_form_responses(
                ids, filter_query=FormResponseFilterQuery(data_owner_identifier=value)
            ),
        )
        assert {i["response_id"] for i in page.items} == expected, value
    await case.page(
        "sorted ascending",
        lambda: postgres.get_form_responses(
            ids, sort=SortRequest(sort_by="created_at", sort_order=SortOrder.ASCENDING)
        ),
        size=2,
    )
    await case.page("deletion requests", lambda: postgres.get_deletion_requests(ids))
    await case.page(
        "submissions of a", lambda: postgres.get_user_submissions(ids, user_a)
    )
    await case.page(
        "deletion requests of a",
        lambda: postgres.get_user_submissions(ids, user_a, request_for_deletion=True),
    )
    await case.page(
        "responders", lambda: postgres.list(ids, False, data_subjects=True)
    )
    # the responders' email filter is literal text too
    for value, expected in (
        ("A@EXAMPLE", {"a@example.com"}),
        ("a.e", set()),
        ("[", set()),
    ):
        page = await case.page(
            f"responders filter {value}",
            lambda: postgres.list(
                ids, False, FormResponseFilterQuery(email=value), data_subjects=True
            ),
        )
        assert {i["email"] for i in page.items} == expected, value
    stored = {r: await postgres.get_response(r) for r in ("r1", "r2", "r3")}
    await case.steps(
        postgres,
        [
            ("count_responses_with_answers_by_form_ids", lambda: (ids,)),
            ("count_deletion_requests_by_form_ids", lambda: (ids,)),
            ("count_responses_for_form_ids", lambda: (ids,)),
            ("get_deletion_requests_count_in_workspace", lambda: (ids,)),
            (
                "get_deletion_requests_count_in_workspace",
                lambda: (legacy(ws, "missing"),),
            ),
            ("list_recent_by_form_id", lambda: (f1, 2)),
            ("list_deletion_requests_for_form_ids", lambda: (ids,)),
            ("list_by_form_id", lambda: (f2,)),
            ("find_deletion_request_for", lambda: (stored["r3"],)),
            ("find_deletion_request_for", lambda: (stored["r1"],)),
            ("find_deletion_request_for", lambda: (stored["r2"],)),
            ("get_all_expiring_responses", lambda: ()),
            ("get_response", lambda: ("r2",)),
            ("get_response", lambda: ("nope",)),
        ],
    )
    # writes
    saved = await postgres.save_form_response(
        oid(3),
        StandardFormResponse(answers={}, dataOwnerIdentifier="c@example.com"),
        ws,
    )
    dumped = saved.model_dump()  # answers is an encrypted blob: not JSON, not equal
    for key in (
        "id",
        "created_at",
        "updated_at",
        "submission_uuid",
        "answers",
        "form_id",
    ):
        dumped.pop(key, None)
    await case.step("a submitted response", lambda: _value(dumped))
    r1 = await postgres.get_response("r1")
    await case.steps(
        postgres,
        [
            (
                "mark_deletion_requests_success_except",
                lambda: (f1, None, ["zzz"], at(9)),
            ),
            ("find_deletion_request_for", lambda: (stored["r3"],)),
            ("delete_form_response", lambda: (r1,)),
            ("get_response", lambda: ("r1",)),
            ("delete_by_form_id_except", lambda: (f1, ["r2"])),
            ("list_by_form_id", lambda: (f1,)),
            ("delete_response", lambda: ("r3",)),
            ("delete_deletion_requests", lambda: ("f1",)),
            ("list_deletion_requests_for_form_ids", lambda: (ids,)),
            ("delete_by_form_ids", lambda: (["f2", "orphan"],)),
            ("count_responses_for_form_ids", lambda: (ids,)),
            ("delete_deletion_requests_by_form_ids", lambda: (list(ids.form_ids),)),
        ],
    )
    case.check()


async def _value(value):
    return value


async def test_workspace_responders_and_tags(sessions):
    ws = oid(1)
    postgres = PostgresWorkspaceRespondersRepository(sessions)
    case = pinned("workspace_responders_and_tags")
    tag_id = oid(7)
    await case.step("a tag", lambda: postgres.create_workspace_tag(ws, "vip"))
    await case.steps(
        postgres,
        [
            ("create_workspace_tag", lambda: (ws, "vip")),  # idempotent on title
            ("get_workspace_tags", lambda: (ws,)),
            ("get_workspace_tags", lambda: (oid(8),)),
            ("get_responder_by_email_and_workspace_id", lambda: (ws, "a@example.com")),
            ("get_responder_by_email_and_workspace_id", lambda: (ws, "a@example.com")),
            # patches the existing record; only non-empty fields change
            ("patch_responder", lambda: (ws, "a@example.com", {"team": "x"}, None)),
            ("patch_responder", lambda: (ws, "a@example.com", None, [tag_id])),
            ("patch_responder", lambda: (ws, "a@example.com", {}, [])),
            # creates one that does not exist yet
            ("patch_responder", lambda: (ws, "b@example.com", None, [tag_id])),
        ],
    )
    stored = await postgres.get_responder_by_email_and_workspace_id(ws, "a@example.com")
    assert (stored.metadata, stored.tags) == ({"team": "x"}, [tag_id])
    assert len(await postgres.get_workspace_tags(ws)) == 1
    case.check()


async def test_responder_groups(sessions):
    ws = oid(1)
    repo = PostgresResponderGroupsRepository(sessions)
    group = await repo.create_group(ws, "Team", "desc", ".*@team.com")
    assert (group.name, group.description, group.regex) == (
        "Team",
        "desc",
        ".*@team.com",
    )
    assert isinstance(await repo.create_group(ws, "x", "d" * 281), dict)
    await repo.add_emails_to_group(group.id, ["a@x.com", "b@x.com", "a@x.com"])
    await repo.add_group_to_form("f1", group.id)
    await repo.add_group_to_form("f1", group.id)  # idempotent
    await repo.add_groups_to_form("f2", [group.id])
    info = await repo.get_emails_in_group(group.id)
    assert sorted(info["emails"]) == ["a@x.com", "b@x.com"]
    assert sorted(info["forms"]) == ["f1", "f2"]
    groups = await repo.get_groups_in_workspace(ws)
    assert [g.name for g in groups] == ["Team"] and sorted(groups[0].forms) == [
        "f1",
        "f2",
    ]
    assert await repo.get_group_in_workspace(ws, group.id) is not None
    assert await repo.get_group_in_workspace(oid(2), group.id) is None
    assert (await repo.get_groups_by_form_ids(["f1", "zz"]))["f1"][0]["name"] == "Team"
    assert await repo.get_form_ids_accessible_to(["f1", "f2", "f3"], "b@x.com") == {
        "f1",
        "f2",
    }
    assert await repo.get_form_ids_accessible_to(["f1"], "who@team.com") == {"f1"}
    assert await repo.get_form_ids_accessible_to(["f1"], "who@else.com") == set()
    await repo.remove_emails_from_group(group.id, ["a@x.com"])
    await repo.remove_group_from_form("f2", group.id)
    updated = await repo.update_group(ws, "Team2", None, ["c@x.com"], group.id, None)
    assert updated.name == "Team2" and updated.regex is None
    info = await repo.get_emails_in_group(group.id)
    assert (info["emails"], info["forms"]) == (["c@x.com"], ["f1"])
    assert await repo.get_emails_in_group(oid(3)) is None
    await repo.delete_workspace_form_groups("f1")
    assert (await repo.get_emails_in_group(group.id))["forms"] == []
    await repo.remove_responder_group(group.id)
    assert await repo.get_emails_in_group(group.id) is None
    gone = await repo.create_group(ws, "Gone")
    await repo.add_emails_to_group(gone.id, ["z@x.com"])
    await repo.delete_responder_groups([ws])
    assert await repo.get_groups_in_workspace(ws) == []


async def test_save_internal_answers_is_conditional_on_the_version(sessions):
    """Optimistic concurrency for staff edits: the write applies only against
    the expected version, touches nothing but the three internal keys, and
    returns None on a stale version."""
    from common.models.standard_form import InternalAnswerMeta

    postgres = responses_repo(sessions)
    case = pinned("save_internal_answers_is_conditional_on_the_version")
    seed_response = response("f1", "r1", 1, answers={"a": {"text": "respondent"}})
    await seed(postgres, seed_response)

    def edit(version, value):
        edited = seed_response.model_copy(deep=True)
        edited.answers = {"a": {"text": "must not be written"}}
        edited.internal_answers = b"v1:" + value.encode()
        edited.internal_answers_meta = {
            "x": InternalAnswerMeta(updated_by="u1", updated_at=at(5))
        }
        edited.internal_answers_version = version + 1
        return edited

    await case.steps(
        postgres,
        [
            ("save_internal_answers", lambda: (edit(0, "first"), 0)),
            ("save_internal_answers", lambda: (edit(0, "stale"), 0)),  # None
            ("save_internal_answers", lambda: (edit(1, "second"), 1)),
            ("save_internal_answers", lambda: (edit(7, "wrong"), 7)),  # None
            ("get_response", lambda: ("r1",)),
        ],
    )
    assert await postgres.save_internal_answers(edit(0, "stale"), 0) is None
    stored = await postgres.get_response("r1")
    assert stored.internal_answers_version == 2
    assert stored.internal_answers == b"v1:second"
    assert "respondent" in str(stored.answers)
    assert "must not be written" not in str(stored.answers)
    missing = edit(0, "x")
    missing.response_id = "nope"
    assert await postgres.save_internal_answers(missing, 0) is None
    case.check()


async def test_add_respondent_feedback_appends(sessions):
    """Respondent feedback is an append-only history: the entry is added after
    the earlier ones (also to a response saved before the field existed,
    stored as null), nothing else is touched and None comes back for a
    response that is gone."""
    from common.models.standard_form import RespondentFeedback

    postgres = responses_repo(sessions)
    case = pinned("add_respondent_feedback_appends")
    seed_response = response("f1", "r1", 1, answers={"a": {"text": "respondent"}})
    await seed(postgres, seed_response)
    gone = response("f1", "nope", 2)  # never stored

    def entry(n, status=None, message=None):
        return RespondentFeedback(
            id=f"e{n}",
            status=status,
            message=message,
            created_at=at(10 + n),
            created_by="u1",
            created_by_email="staff@example.com",
        )

    await case.steps(
        postgres,
        [
            (
                "add_respondent_feedback",
                lambda: (seed_response, entry(1, status="Selected")),
            ),
            (
                "add_respondent_feedback",
                lambda: (seed_response, entry(2, message=b"v1:x")),
            ),
            ("add_respondent_feedback", lambda: (gone, entry(3))),  # None
            ("get_response", lambda: ("r1",)),
        ],
    )
    stored = await postgres.get_response("r1")
    assert [e.id for e in stored.respondent_feedback] == ["e1", "e2"]
    assert stored.respondent_feedback[0].status == "Selected"
    assert stored.respondent_feedback[1].message == b"v1:x"
    assert stored.respondent_feedback[1].created_at == at(12)
    assert "respondent" in str(stored.answers)
    assert await postgres.add_respondent_feedback(gone, entry(4)) is None
    case.check()


async def test_responses_are_read_per_workspace(sessions):
    """#768: one provider form in two workspaces. Every scoped read returns
    the scope's workspace's responses (and deletion requests) only; unstamped
    ones count only where the form is the workspace's alone
    (``legacy_form_ids``)."""
    a, b = oid(1), oid(2)
    await container.form_repo().save_form(FormDocument(form_id="p1", title="Provider"))
    for workspace, user in ((a, "ua"), (b, "ub")):
        await container.workspace_form_repo().save(
            WorkspaceFormDocument(workspace_id=workspace, form_id="p1", user_id=user)
        )
    postgres = responses_repo(sessions)
    case = pinned("responses_are_read_per_workspace")

    def notice(minutes):
        return dict(
            provider="self",
            ai_notice_shown_at=at(minutes),
            ai_notice_provider_name="OpenAI",
        )

    await seed(
        postgres,
        response("p1", "a1", 1, answers={}, workspace_id=a, **notice(1)),
        response("p1", "a2", 2, answers={}, workspace_id=a, dataOwnerIdentifier="r@x"),
        response("p1", "b1", 3, answers={}, workspace_id=b, **notice(3)),
        response("p1", "b2", 4, answers={}, workspace_id=b, dataOwnerIdentifier="r@x"),
        response("p1", "old", 5, answers={}),  # before #768: ambiguous here
    )
    for response_id in ("a2", "b2"):
        await postgres.add_deletion_request(
            await postgres.get_response(response_id), response_id
        )
    in_a, in_b = ResponseScope(a, ("p1",)), ResponseScope(b, ("p1",))
    user = User(id=str(oid(3)), sub="r@x")
    for name, scope, own, importer in (
        ("a", in_a, {"a1", "a2"}, "ua"),
        ("b", in_b, {"b1", "b2"}, "ub"),
    ):
        page = await case.page(
            f"responses in {name}", lambda: postgres.get_form_responses(scope)
        )
        assert {i["response_id"] for i in page.items} == own
        requests = await case.page(
            f"deletion requests in {name}", lambda: postgres.get_deletion_requests(scope)
        )
        assert {i["response_id"] for i in requests.items} == own & {"a2", "b2"}
        assert {i["form_imported_by"] for i in requests.items} == {importer}
        mine = await case.page(
            f"submissions in {name}", lambda: postgres.get_user_submissions(scope, user)
        )
        assert {i["response_id"] for i in mine.items} == own & {"a2", "b2"}
        responders = await case.page(
            f"responders in {name}",
            lambda: postgres.list(scope, False, data_subjects=True),
        )
        assert [r["responses"] for r in responders.items] == [1]
        await case.steps(
            postgres,
            [
                ("count_responses_with_answers_by_form_ids", lambda: (scope,)),
                ("count_deletion_requests_by_form_ids", lambda: (scope,)),
                ("count_responses_for_form_ids", lambda: (scope,)),
                ("get_deletion_requests_count_in_workspace", lambda: (scope,)),
                ("list_recent_by_form_id", lambda: (scope, 10)),
                ("list_by_form_id", lambda: (scope,)),
                ("list_deletion_requests_for_form_ids", lambda: (scope,)),
                ("list_recent_with_ai_notice", lambda: (scope, "OpenAI", at(0), 10)),
                ("count_with_ai_notice", lambda: (scope, "OpenAI", at(0))),
            ],
        )
        assert await postgres.count_responses_for_form_ids(scope) == 2
        assert {r.response_id for r in await postgres.list_by_form_id(scope)} == own
        assert await postgres.count_with_ai_notice(scope, "OpenAI", at(0)) == 1
    # the unstamped one is the workspace's when the form is its alone
    only_a = ResponseScope(a, ("p1",), ("p1",))
    assert await postgres.count_responses_for_form_ids(only_a) == 3
    # an import refresh and an unlink touch the scope's workspace only
    await case.steps(
        postgres,
        [
            ("delete_by_form_id_except", lambda: (in_a, ["a1"])),
            ("mark_deletion_requests_success_except", lambda: (in_a, None, [], at(9))),
            ("list_by_form_id", lambda: (in_b,)),
            ("delete_in_scope", lambda: (in_b,)),
            ("list_by_form_id", lambda: (in_a,)),
            ("list_by_form_id", lambda: (in_b,)),
            ("list_deletion_requests_for_form_ids", lambda: (in_b,)),
        ],
    )
    assert [r.response_id for r in await postgres.list_by_form_id(in_a)] == ["a1"]
    assert await postgres.list_by_form_id(in_b) == []
    assert (await postgres.get_response("old")) is not None
    case.check()


async def test_writes_to_one_workspaces_copy_never_touch_anothers(sessions):
    """#768: workspaces A and B each hold a copy of the same provider
    response (same response_id). Internal answers, feedback, a respondent's
    edit and a deletion go to the copy they were given, by its id; B's copy
    stays exactly as it was."""
    from common.models.standard_form import InternalAnswerMeta, RespondentFeedback

    a, b = oid(1), oid(2)
    postgres = responses_repo(sessions)
    case = pinned("writes_to_one_workspaces_copy_never_touch_anothers")

    def copy(workspace_id):
        return response(
            "p1",
            "shared",
            1,
            answers={"q": {"text": "original"}},
            workspace_id=workspace_id,
            dataOwnerIdentifier="r@x",
            provider="google",
        )

    in_a, in_b = copy(a), copy(b)
    await seed(postgres, in_a, in_b)
    await seed(postgres, response("p1", "legacy", 2, answers={}))  # before #768
    await postgres.add_deletion_request(in_b, "shared")
    copies = await postgres.list_by_response_id("shared")
    assert {c.workspace_id for c in copies} == {a, b}
    b_before = strip(next(c for c in copies if c.workspace_id == b))
    assert (await postgres.find_deletion_request_for(in_b)).workspace_id == b
    assert await postgres.find_deletion_request_for(in_a) is None
    assert await postgres.count_unstamped("p1") == 1

    edited = in_a.model_copy(deep=True)
    edited.internal_answers = b"v1:internal"
    edited.internal_answers_meta = {
        "x": InternalAnswerMeta(updated_by="u1", updated_at=at(5))
    }
    edited.internal_answers_version = 1
    feedback = RespondentFeedback(
        id="e1", status="Selected", created_at=at(6), created_by="u1"
    )
    user = User(id=str(oid(3)), sub="r@x")
    await case.steps(
        postgres,
        [
            ("save_internal_answers", lambda: (edited, 0)),
            ("add_respondent_feedback", lambda: (in_a, feedback)),
        ],
    )
    await postgres.patch_form_response(
        "p1",
        in_a.id,
        StandardFormResponse(answers={"q": {"text": "edited"}}),
        a,
        user,
    )

    copies = {c.workspace_id: c for c in await postgres.list_by_response_id("shared")}
    assert copies[a].internal_answers == b"v1:internal"
    assert [e.id for e in copies[a].respondent_feedback] == ["e1"]
    assert "edited" not in str(copies[a].answers)  # encrypted under A now
    assert strip(copies[b]) == b_before

    await postgres.delete_form_response(in_a)
    copies = await postgres.list_by_response_id("shared")
    assert [c.workspace_id for c in copies] == [b]
    assert strip(copies[0]) == b_before
    # B's deletion request was not completed by deleting A's copy
    request = await postgres.find_deletion_request_for(in_b)
    assert request.status == DeletionRequestStatus.PENDING
    await postgres.delete_form_response(in_b)
    assert await postgres.list_by_response_id("shared") == []
    assert (
        await postgres.find_deletion_request_for(in_b)
    ).status == DeletionRequestStatus.SUCCESS
    case.check()
