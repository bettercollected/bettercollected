"""The Postgres twins of the responses, actions, ai and analytics repositories
behave like the Mongo originals. The forms-group data the responses twin
composes over lives in Mongo here (routed repositories are Mongo instances).
Skipped unless DATABASE_URL points at a *_test database.
"""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.filter_queries.form_responses import FormResponseFilterQuery
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.ai_preference_memory_repository import (
    AIPreferenceMemoryRepository,
)
from backend.app.repositories.deletion_requests_repository import (
    DeletionRequestsRepository,
)
from backend.app.repositories.flow_event_repository import FlowEventRepository
from backend.app.repositories.form_ai_insight_repository import FormAIInsightRepository
from backend.app.repositories.form_ai_session_repository import FormAISessionRepository
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.mcp_audit_log_repository import McpAuditLogRepository
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.ai import (
    PostgresAIPreferenceMemoryRepository,
    PostgresFlowEventRepository,
    PostgresFormAIInsightRepository,
    PostgresFormAISessionRepository,
    PostgresMcpAuditLogRepository,
    PostgresWorkspaceAIProfileRepository,
)
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresResponderGroupsRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.workspace_ai_profile_repository import (
    WorkspaceAIProfileRepository,
)
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_responders_repository import (
    WorkspaceRespondersRepository,
)
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    DeletionRequestStatus,
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_responder import WorkspaceResponderDocument
from common.exceptions import NotFoundError
from common.models.standard_form import StandardFormResponse
from common.models.user import User
from tests.app.repositories.test_identity_parity import both_raise
from tests.app.repositories.test_refdata_parity import parity, strip

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def at(minutes):
    return T0 + dt.timedelta(minutes=minutes)


def response(form_id, response_id, minutes, **extra):
    return FormResponseDocument(
        id=PydanticObjectId(),
        form_id=form_id,
        response_id=response_id,
        created_at=at(minutes),
        **extra,
    )


async def seed_both(pairs, method, *documents):
    for repo in pairs:
        for document in documents:
            await getattr(repo, method)(document)


async def pages_equal(mongo_call, postgres_call, size=10):
    with set_page(Page), set_params(Params(page=1, size=size)):
        m, p = await mongo_call(), await postgres_call()
    assert (m.total, m.pages) == (p.total, p.pages)
    assert strip(m.items) == strip(p.items)
    return p


# ------------------------------------------------------------------ responses
async def test_responses_with_the_ai_notice(sessions):
    """#752: only responses submitted here whose page showed the notice for
    this provider name since the setting was turned on."""
    forms, workspace_forms = FormRepository(), WorkspaceFormRepository()
    mongo = FormResponseRepository(crypto=container.crypto())
    postgres = PostgresFormResponseRepository(sessions, forms, workspace_forms)

    def shown(minutes, name="OpenAI", provider="self"):
        return dict(
            answers={},
            provider=provider,
            ai_notice_shown_at=at(minutes),
            ai_notice_provider_name=name,
        )

    await seed_both(
        (mongo, postgres),
        "save",
        response("n1", "a1", 10, **shown(9)),
        response("n1", "a2", 20, **shown(19)),
        response("n1", "a3", 30, **shown(29, name="Google Gemini")),
        response("n1", "a4", 40, answers={}, provider="self"),  # never saw it
        response("n1", "a5", 50, **shown(2)),  # shown before the setting
        response("n1", "a6", 60, **shown(59, provider="google")),  # imported
        response("n2", "a7", 70, **shown(69)),  # another form
    )
    calls = [
        ("list_recent_with_ai_notice", lambda: ("n1", "OpenAI", at(5), 10)),
        ("list_recent_with_ai_notice", lambda: ("n1", "OpenAI", at(5), 1)),
        ("list_recent_with_ai_notice", lambda: ("n1", "Google Gemini", at(5), 10)),
        ("count_with_ai_notice", lambda: ("n1", "OpenAI", at(5))),
        ("count_with_ai_notice", lambda: ("n1", "OpenAI", at(0))),
        ("count_with_ai_notice", lambda: ("n3", "OpenAI", at(0))),
    ]
    await parity(mongo, postgres, calls)
    listed = await postgres.list_recent_with_ai_notice("n1", "OpenAI", at(5), 10)
    assert [r.response_id for r in listed] == ["a2", "a1"]
    assert await mongo.count_with_ai_notice("n1", "OpenAI", at(0)) == 3


async def test_response_listings_compose_over_forms(sessions):
    ws = PydanticObjectId()
    # forms-group data, in Mongo only: the twin composes over it
    forms, workspace_forms = FormRepository(), WorkspaceFormRepository()
    for form_id, title in (("f1", "Alpha"), ("f2", "Beta")):
        await forms.save_form(FormDocument(form_id=form_id, title=title))
        await workspace_forms.save(
            WorkspaceFormDocument(workspace_id=ws, form_id=form_id, user_id="importer")
        )
    mongo = FormResponseRepository(crypto=container.crypto())
    postgres = PostgresFormResponseRepository(sessions, forms, workspace_forms)
    await seed_both(
        (mongo, postgres),
        "save",
        response("f1", "r1", 1, answers={}, dataOwnerIdentifier="a@example.com"),
        response("f1", "r2", 2, answers={}, dataOwnerIdentifier="b@example.com"),
        response("f2", "r3", 3, answers={}, dataOwnerIdentifier="a@example.com"),
        response("f1", "r4", 4),  # no answers: a deletion-only stub, not listed
        response("orphan", "r5", 5, answers={}),  # its form is gone: dropped
    )
    for repo in (mongo, postgres):
        for response_id in ("r1", "r3"):
            await repo.add_deletion_request(
                await repo.get_response(response_id), response_id
            )

    ids = ["f1", "f2", "orphan", "missing"]
    user_a = User(id=str(PydanticObjectId()), sub="a@example.com")
    await pages_equal(
        lambda: mongo.get_form_responses(ids),
        lambda: postgres.get_form_responses(ids),
    )
    page = await pages_equal(
        lambda: mongo.get_form_responses(ids, data_owner_identifier="a@example.com"),
        lambda: postgres.get_form_responses(ids, data_owner_identifier="a@example.com"),
    )
    assert {i["response_id"] for i in page.items} == {"r1", "r3"}
    assert (
        next(i for i in page.items if i["response_id"] == "r3")["status"] == "pending"
    )
    assert (
        next(i for i in page.items if i["response_id"] == "r1")["form_title"] == "Alpha"
    )
    await pages_equal(
        lambda: mongo.get_form_responses(
            ids, filter_query=FormResponseFilterQuery(data_owner_identifier="^b@")
        ),
        lambda: postgres.get_form_responses(
            ids, filter_query=FormResponseFilterQuery(data_owner_identifier="^b@")
        ),
    )
    await pages_equal(
        lambda: mongo.get_form_responses(
            ids, sort=SortRequest(sort_by="created_at", sort_order=SortOrder.ASCENDING)
        ),
        lambda: postgres.get_form_responses(
            ids, sort=SortRequest(sort_by="created_at", sort_order=SortOrder.ASCENDING)
        ),
        size=2,
    )
    await pages_equal(  # the Mongo original lives on the static DeletionRequestsRepository
        lambda: DeletionRequestsRepository.get_deletion_requests(ids),
        lambda: postgres.get_deletion_requests(ids),
    )
    await pages_equal(
        lambda: mongo.get_user_submissions(ids, user_a),
        lambda: postgres.get_user_submissions(ids, user_a),
    )
    await pages_equal(
        lambda: mongo.get_user_submissions(ids, user_a, request_for_deletion=True),
        lambda: postgres.get_user_submissions(ids, user_a, request_for_deletion=True),
    )
    await pages_equal(
        lambda: mongo.list(ids, False, data_subjects=True),
        lambda: postgres.list(ids, False, data_subjects=True),
    )
    await parity(
        mongo,
        postgres,
        [
            ("count_responses_with_answers_by_form_ids", lambda: (ids,)),
            ("count_deletion_requests_by_form_ids", lambda: (ids,)),
            ("count_responses_for_form_ids", lambda: (ids,)),
            ("get_deletion_requests_count_in_workspace", lambda: (ids,)),
            ("get_deletion_requests_count_in_workspace", lambda: (["missing"],)),
            ("list_recent_by_form_id", lambda: ("f1", 2)),
            ("list_deletion_requests_for_form_ids", lambda: (ids,)),
            ("list_by_form_id", lambda: ("f2",)),
            ("find_deletion_request_by_response_id", lambda: ("r3",)),
            ("find_deletion_request_by_response_id", lambda: ("r1",)),
            ("get_all_expiring_responses", lambda: ()),
            ("get_response", lambda: ("r2",)),
            ("get_response", lambda: ("nope",)),
            ("verify_response_exists_in_workspace", lambda: (ws, "r1")),
        ],
    )
    await both_raise(
        HTTPException,
        lambda: mongo.verify_response_exists_in_workspace(PydanticObjectId(), "r1"),
        lambda: postgres.verify_response_exists_in_workspace(PydanticObjectId(), "r1"),
    )
    await both_raise(
        HTTPException,
        lambda: mongo.verify_response_exists_in_workspace(ws, "r5"),
        lambda: postgres.verify_response_exists_in_workspace(ws, "r5"),
    )
    # writes
    submitted = []
    for repo in (mongo, postgres):
        saved = await repo.save_form_response(
            PydanticObjectId(),
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
        submitted.append(dumped)
    assert submitted[0] == submitted[1]
    await parity(
        mongo,
        postgres,
        [
            (
                "mark_deletion_requests_success_except",
                lambda: ("f1", None, ["zzz"], at(9)),
            ),
            ("find_deletion_request_by_response_id", lambda: ("r3",)),
            ("delete_form_response", lambda: ("f1", "r1")),
            ("get_response", lambda: ("r1",)),
            ("delete_by_form_id_except", lambda: ("f1", ["r2"])),
            ("list_by_form_id", lambda: ("f1",)),
            ("delete_response", lambda: ("r3",)),
            ("delete_deletion_requests", lambda: ("f1",)),
            ("list_deletion_requests_for_form_ids", lambda: (ids,)),
            ("delete_by_form_ids", lambda: (["f2", "orphan"],)),
            ("count_responses_for_form_ids", lambda: (ids,)),
            ("delete_deletion_requests_by_form_ids", lambda: (ids,)),
        ],
    )


async def test_workspace_responders_and_tags(sessions):
    ws = PydanticObjectId()
    mongo, postgres = (
        WorkspaceRespondersRepository(),
        PostgresWorkspaceRespondersRepository(sessions),
    )
    tags = [
        strip(await repo.create_workspace_tag(ws, "vip")) for repo in (mongo, postgres)
    ]
    assert tags[0] == tags[1]
    await parity(
        mongo,
        postgres,
        [
            ("create_workspace_tag", lambda: (ws, "vip")),  # idempotent on title
            ("get_workspace_tags", lambda: (ws,)),
            ("get_workspace_tags", lambda: (PydanticObjectId(),)),
            ("get_responder_by_email_and_workspace_id", lambda: (ws, "a@example.com")),
            ("get_responder_by_email_and_workspace_id", lambda: (ws, "a@example.com")),
        ],
    )


async def test_responder_groups(sessions):
    ws = PydanticObjectId()
    mongo, postgres = ResponderGroupsRepository(), PostgresResponderGroupsRepository(
        sessions
    )
    created = [
        await repo.create_group(ws, "Team", "desc", ".*@team.com")
        for repo in (mongo, postgres)
    ]
    assert strip(created[0]) == strip(created[1])
    assert isinstance(await postgres.create_group(ws, "x", "d" * 281), dict)
    for repo, group in zip((mongo, postgres), created):
        await repo.add_emails_to_group(group.id, ["a@x.com", "b@x.com", "a@x.com"])
        await repo.add_group_to_form("f1", group.id)
        await repo.add_group_to_form("f1", group.id)  # idempotent
        await repo.add_groups_to_form("f2", [group.id])
    # relation documents get derived ids, so both stores hold identical rows
    m_links = await mongo.get_emails_in_group(created[0].id)
    p_links = await postgres.get_emails_in_group(created[1].id)
    assert (
        sorted(m_links["emails"]) == sorted(p_links["emails"]) == ["a@x.com", "b@x.com"]
    )
    assert sorted(m_links["forms"]) == sorted(p_links["forms"]) == ["f1", "f2"]
    for repo, group in zip((mongo, postgres), created):
        groups = await repo.get_groups_in_workspace(ws)
        assert [g.name for g in groups] == ["Team"] and sorted(groups[0].forms) == [
            "f1",
            "f2",
        ]
        assert await repo.get_group_in_workspace(ws, group.id) is not None
        assert await repo.get_group_in_workspace(PydanticObjectId(), group.id) is None
        assert (await repo.get_groups_by_form_ids(["f1", "zz"]))["f1"][0][
            "name"
        ] == "Team"
        assert await repo.get_form_ids_accessible_to(["f1", "f2", "f3"], "b@x.com") == {
            "f1",
            "f2",
        }
        assert await repo.get_form_ids_accessible_to(["f1"], "who@team.com") == {"f1"}
        assert await repo.get_form_ids_accessible_to(["f1"], "who@else.com") == set()
        await repo.remove_emails_from_group(group.id, ["a@x.com"])
        await repo.remove_group_from_form("f2", group.id)
        updated = await repo.update_group(
            ws, "Team2", None, ["c@x.com"], group.id, None
        )
        assert updated.name == "Team2" and updated.regex is None
        info = await repo.get_emails_in_group(group.id)
        assert (info["emails"], info["forms"]) == (["c@x.com"], ["f1"])
        assert await repo.get_emails_in_group(PydanticObjectId()) is None
        await repo.delete_workspace_form_groups("f1")
        assert (await repo.get_emails_in_group(group.id))["forms"] == []
        await repo.remove_responder_group(group.id)
        assert await repo.get_emails_in_group(group.id) is None
    for repo in (mongo, postgres):
        g = await repo.create_group(ws, "Gone")
        await repo.add_emails_to_group(g.id, ["z@x.com"])
        await repo.delete_responder_groups([ws])
        assert await repo.get_groups_in_workspace(ws) == []


# --------------------------------------------------------------------- actions
async def test_actions(sessions):
    ws = PydanticObjectId()
    user = User(id=str(PydanticObjectId()), sub="u@example.com")
    mongo = ActionRepository(crypto=container.crypto())
    postgres = PostgresActionRepository(sessions, container.crypto())

    def dto(name):
        return ActionDto(
            name=name, title=name, action_code="print(1)", secrets=None, parameters=None
        )

    created = [
        await repo.create_action(ws, dto("notify"), user) for repo in (mongo, postgres)
    ]
    assert strip(created[0]) == strip(created[1])
    globals_ = [
        await repo.create_global_action(dto("global"), user)
        for repo in (mongo, postgres)
    ]
    assert strip(globals_[0]) == strip(globals_[1])
    for repo, action in zip((mongo, postgres), created):
        assert strip(await repo.get_action_by_id(action.id)) == strip(action)
        assert len(await repo.get_all_actions()) == 2
        assert [a.name for a in await repo.get_actions_by_ids([action.id])] == [
            "notify"
        ]
        wa = await repo.create_action_in_workspace_from_action(ws, action.id, "cred")
        assert dict(wa.secrets[0])["value"] == "cred"  # stored as a plain dict
        wa2 = await repo.create_action_in_workspace_from_action(ws, action.id)
        assert wa2.id == wa.id and wa2.secrets is None
        assert (await repo.get_workspace_action(ws, action.id)).id == wa.id
        assert await repo.get_workspace_action(PydanticObjectId(), action.id) is None
        assert await repo.delete_action(action.id) == action.id
        assert await repo.get_action_by_id(action.id) is None


# ------------------------------------------------------------ ai and analytics
async def test_ai_and_analytics(sessions):
    ws = PydanticObjectId()
    await parity(
        FlowEventRepository(),
        PostgresFlowEventRepository(sessions),
        [
            ("add", lambda: ("f1", "s1", "p1", "p2")),
            ("add", lambda: ("f1", "s1", "p2", "p3")),
            ("list_by_form_id", lambda: ("f1",)),
            ("list_by_form_id", lambda: ("f2",)),
        ],
    )
    insight = FormAIInsightDocument(
        id=PydanticObjectId(),
        workspace_id=ws,
        form_id="f1",
        payload={"k": 1},
        response_count=3,
        total_responses=3,
        generated_at=at(1),
    )
    await parity(
        FormAIInsightRepository(),
        PostgresFormAIInsightRepository(sessions),
        [
            ("find", lambda: (ws, "f1")),
            ("save", lambda: (insight,)),
            ("find", lambda: (ws, "f1")),
            ("find", lambda: (ws, "f2")),
        ],
    )
    session = FormAISessionDocument(
        id=PydanticObjectId(), workspace_id=ws, form_id="f1", user_id="u1", messages=[]
    )
    mongo_s, postgres_s = FormAISessionRepository(), PostgresFormAISessionRepository(
        sessions
    )
    await parity(
        mongo_s,
        postgres_s,
        [("save", lambda: (session,)), ("get_or_404", lambda: (session.id,))],
    )
    missing = PydanticObjectId()
    await both_raise(
        NotFoundError,
        lambda: mongo_s.get_or_404(missing),
        lambda: postgres_s.get_or_404(missing),
    )
    profile = WorkspaceAIProfileDocument(
        id=PydanticObjectId(), workspace_id=ws, about="us"
    )
    await parity(
        WorkspaceAIProfileRepository(),
        PostgresWorkspaceAIProfileRepository(sessions),
        [
            ("find_by_workspace", lambda: (ws,)),
            ("save", lambda: (profile,)),
            ("find_by_workspace", lambda: (ws,)),
        ],
    )
    memory = UserAIPreferenceMemoryDocument(
        id=PydanticObjectId(), workspace_id=ws, user_id="u1", entries=[{"text": "x"}]
    )
    await parity(
        AIPreferenceMemoryRepository(),
        PostgresAIPreferenceMemoryRepository(sessions),
        [
            ("save", lambda: (memory,)),
            ("find", lambda: (ws, "u1")),
            ("find", lambda: (ws, "u2")),
        ],
    )
    mongo_l, postgres_l = McpAuditLogRepository(), PostgresMcpAuditLogRepository(
        sessions
    )
    for repo in (mongo_l, postgres_l):
        await repo.add(
            workspace_id=ws, key_id="k", tool="update_form", ok=True, at=at(1)
        )
    assert strip(await mongo_l.list_by_workspace(ws)) == strip(
        await postgres_l.list_by_workspace(ws)
    )


async def test_save_internal_answers_is_conditional_on_the_version(sessions):
    """Optimistic concurrency for staff edits: both stores apply the write only
    against the expected version, touch nothing but the three internal keys,
    and return None on a stale version."""
    from common.models.standard_form import InternalAnswerMeta

    forms, workspace_forms = FormRepository(), WorkspaceFormRepository()
    mongo = FormResponseRepository(crypto=container.crypto())
    postgres = PostgresFormResponseRepository(sessions, forms, workspace_forms)
    seed = response("f1", "r1", 1, answers={"a": {"text": "respondent"}})
    await seed_both((mongo, postgres), "save", seed)

    def edit(version, value):
        edited = seed.model_copy(deep=True)
        edited.answers = {"a": {"text": "must not be written"}}
        edited.internal_answers = b"v1:" + value.encode()
        edited.internal_answers_meta = {
            "x": InternalAnswerMeta(updated_by="u1", updated_at=at(5))
        }
        edited.internal_answers_version = version + 1
        return edited

    await parity(
        mongo,
        postgres,
        [
            ("save_internal_answers", lambda: (edit(0, "first"), 0)),
            ("save_internal_answers", lambda: (edit(0, "stale"), 0)),  # None
            ("save_internal_answers", lambda: (edit(1, "second"), 1)),
            ("save_internal_answers", lambda: (edit(7, "wrong"), 7)),  # None
            ("get_response", lambda: ("r1",)),
        ],
    )
    for repo in (mongo, postgres):
        assert await repo.save_internal_answers(edit(0, "stale"), 0) is None
        stored = await repo.get_response("r1")
        assert stored.internal_answers_version == 2
        assert stored.internal_answers == b"v1:second"
        assert "respondent" in str(stored.answers)
        assert "must not be written" not in str(stored.answers)
        missing = edit(0, "x")
        missing.response_id = "nope"
        assert await repo.save_internal_answers(missing, 0) is None


async def test_add_respondent_feedback_appends_on_both_stores(sessions):
    """Respondent feedback is an append-only history: both stores add the
    entry after the earlier ones (also to a response saved before the field
    existed, stored as null), touch nothing else and return None for a
    response that is gone."""
    from common.models.standard_form import RespondentFeedback

    forms, workspace_forms = FormRepository(), WorkspaceFormRepository()
    mongo = FormResponseRepository(crypto=container.crypto())
    postgres = PostgresFormResponseRepository(sessions, forms, workspace_forms)
    seed = response("f1", "r1", 1, answers={"a": {"text": "respondent"}})
    await seed_both((mongo, postgres), "save", seed)

    def entry(n, status=None, message=None):
        return RespondentFeedback(
            id=f"e{n}",
            status=status,
            message=message,
            created_at=at(10 + n),
            created_by="u1",
            created_by_email="staff@example.com",
        )

    await parity(
        mongo,
        postgres,
        [
            ("add_respondent_feedback", lambda: ("r1", entry(1, status="Selected"))),
            ("add_respondent_feedback", lambda: ("r1", entry(2, message=b"v1:x"))),
            ("add_respondent_feedback", lambda: ("nope", entry(3))),  # None
            ("get_response", lambda: ("r1",)),
        ],
    )
    for repo in (mongo, postgres):
        stored = await repo.get_response("r1")
        assert [e.id for e in stored.respondent_feedback] == ["e1", "e2"]
        assert stored.respondent_feedback[0].status == "Selected"
        assert stored.respondent_feedback[1].message == b"v1:x"
        assert stored.respondent_feedback[1].created_at == at(12)
        assert "respondent" in str(stored.answers)
        assert await repo.add_respondent_feedback("nope", entry(4)) is None
