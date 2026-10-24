"""The ai repositories (AI insights, chat sessions, profiles, preference
memories, the MCP audit log, form prompts, Idempotency-Key records), Postgres
only since 4.1. The behaviour they had under the dual run (where these steps
ran against the Mongo originals too) stays pinned here. Skipped unless
DATABASE_URL points at a *_test database."""

import asyncio
import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.repositories.postgres.ai import (
    PostgresAIPreferenceMemoryRepository,
    PostgresCreateFormPromptRepository,
    PostgresFormAIInsightRepository,
    PostgresFormAISessionRepository,
    PostgresIdempotencyRepository,
    PostgresMcpAuditLogRepository,
    PostgresWorkspaceAIProfileRepository,
)
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.api_idempotency_record import ApiIdempotencyRecordDocument
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.db.models import ApiIdempotencyKeyRow, McpAuditLogRow
from common.exceptions import NotFoundError
from common.records import RecordId

WORKSPACE = RecordId("65f0a1b2c3d4e5f600000001")
OTHER_WORKSPACE = RecordId("65f0a1b2c3d4e5f600000002")
UNKNOWN = RecordId("65f0a1b2c3d4e5f6000000ff")
WHEN = dt.datetime(2026, 5, 6, 7, 8, 9, 123456, tzinfo=dt.timezone.utc)


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


# -- form AI insights ------------------------------------------------------------


def _insight(form_id, workspace_id=WORKSPACE, **payload):
    return FormAIInsightDocument(
        workspace_id=workspace_id,
        form_id=form_id,
        payload={"summary": "s", "themes": [{"name": "t", "count": 2}], **payload},
        response_count=3,
        total_responses=5,
        generated_by="user-1",
        generated_at=WHEN,
    )


async def test_form_ai_insights_one_per_workspace_and_form(sessions):
    repo = PostgresFormAIInsightRepository(sessions)
    assert await repo.find(WORKSPACE, "form-1") is None
    first = await repo.save(_insight("form-1"))
    assert first.id is not None
    found = await repo.find(WORKSPACE, "form-1")
    assert found.id == first.id and found.generated_at == WHEN
    assert isinstance(found.workspace_id, RecordId) and found.workspace_id == WORKSPACE
    assert await repo.find(OTHER_WORKSPACE, "form-1") is None
    assert await repo.find(WORKSPACE, "form-2") is None
    assert await repo.find(str(WORKSPACE), "form-1") is not None

    # regenerated: the same document, replaced
    first.payload = {"summary": "again", "nested": {"none": None, "list": []}}
    first.response_count = 4
    await repo.save(first)
    again = await repo.find(WORKSPACE, "form-1")
    assert again.id == first.id
    assert again.payload == {"summary": "again", "nested": {"none": None, "list": []}}
    assert again.response_count == 4 and again.updated_at >= again.created_at

    other = await repo.save(_insight("form-1", OTHER_WORKSPACE, extra=True))
    assert (await repo.find(OTHER_WORKSPACE, "form-1")).id == other.id
    assert (await repo.find(WORKSPACE, "form-1")).id == first.id


# -- form AI sessions ------------------------------------------------------------


def _session(*proposals, form_id="form-1"):
    messages = [{"role": "user", "content": "add a question"}]
    for proposal in proposals:
        messages.append(
            {
                "role": "assistant",
                "content": "here",
                "proposal": {"ops": [{"op": "add"}], **proposal},
            }
        )
    return FormAISessionDocument(
        workspace_id=WORKSPACE,
        form_id=form_id,
        user_id="user-1",
        provider="mock",
        messages=messages,
    )


def _proposals(session):
    return [m["proposal"] for m in session.messages if "proposal" in m]


async def test_form_ai_sessions_and_proposal_updates(sessions):
    repo = PostgresFormAISessionRepository(sessions)
    with pytest.raises(NotFoundError):
        await repo.get_or_404(UNKNOWN)
    chat = await repo.save(
        _session({"id": "p1", "status": "pending"}, {"id": "p2", "status": "pending"})
    )
    stored = await repo.get_or_404(chat.id)
    assert stored.messages == chat.messages and stored.provider == "mock"

    update = repo.update_proposal
    assert await update(chat.id, "p1", {"status": "applied", "at": "t1"}) is True
    # only while the proposal still has the expected status
    assert await update(chat.id, "p1", {"status": "rejected"}, "pending") is False
    assert await update(chat.id, "p2", {"status": "rejected"}, "pending") is True
    # a new key, and nothing else of the message changes
    assert await update(chat.id, "p2", {"attempt": 2}) is True
    # setting what is already there changes nothing: not an update
    assert await update(chat.id, "p1", {"status": "applied", "at": "t1"}) is False
    assert await update(chat.id, "missing", {"status": "x"}) is False
    assert await update(UNKNOWN, "p1", {"status": "x"}) is False
    stored = await repo.get_or_404(chat.id)
    assert _proposals(stored) == [
        {"ops": [{"op": "add"}], "id": "p1", "status": "applied", "at": "t1"},
        {"ops": [{"op": "add"}], "id": "p2", "status": "rejected", "attempt": 2},
    ]
    assert stored.messages[0] == {"role": "user", "content": "add a question"}

    # a chat turn saves the whole session (and keeps the decisions it read)
    stored.messages.append({"role": "user", "content": "thanks", "none": None})
    await repo.save(stored)
    turn = await repo.get_or_404(str(chat.id))
    assert turn.messages[-1] == {"role": "user", "content": "thanks", "none": None}
    assert _proposals(turn)[0]["status"] == "applied"

    # every record carrying the id is matched, each against the status filter
    twice = await repo.save(
        _session(
            {"id": "dup", "status": "pending"},
            {"id": "dup", "status": "applied"},
            form_id="form-2",
        )
    )
    assert await update(twice.id, "dup", {"status": "seen"}, "applied") is True
    assert [p["status"] for p in _proposals(await repo.get_or_404(twice.id))] == [
        "pending",
        "seen",
    ]
    assert await update(twice.id, "dup", {"note": "both"}) is True
    assert [p.get("note") for p in _proposals(await repo.get_or_404(twice.id))] == [
        "both",
        "both",
    ]


# -- workspace AI profiles -------------------------------------------------------


async def test_workspace_ai_profiles(sessions):
    repo = PostgresWorkspaceAIProfileRepository(sessions)
    assert await repo.find_by_workspace(WORKSPACE) is None
    profile = await repo.save(
        WorkspaceAIProfileDocument(workspace_id=WORKSPACE, about="We are kind.")
    )
    found = await repo.find_by_workspace(WORKSPACE)
    assert found.id == profile.id and found.about == "We are kind."
    assert found.guidelines == found.compliance == "" and found.revisions == []
    assert await repo.find_by_workspace(OTHER_WORKSPACE) is None

    found.guidelines = "Short questions."
    found.compliance = "No health data."
    found.updated_by = "user-1"
    found.revisions = [{"about": "We are kind.", "at": WHEN.isoformat(), "by": None}]
    await repo.save(found)
    again = await repo.find_by_workspace(str(WORKSPACE))
    assert (again.id, again.guidelines, again.compliance, again.updated_by) == (
        profile.id,
        "Short questions.",
        "No health data.",
        "user-1",
    )
    assert again.revisions == found.revisions

    other = await repo.save(WorkspaceAIProfileDocument(workspace_id=OTHER_WORKSPACE))
    assert (await repo.find_by_workspace(OTHER_WORKSPACE)).id == other.id


async def test_one_profile_per_workspace(sessions):
    repo = PostgresWorkspaceAIProfileRepository(sessions)
    await repo.save(WorkspaceAIProfileDocument(workspace_id=WORKSPACE))
    with pytest.raises(IntegrityError):
        await repo.save(WorkspaceAIProfileDocument(workspace_id=WORKSPACE))


# -- AI preference memories ------------------------------------------------------


async def test_ai_preference_memories(sessions):
    repo = PostgresAIPreferenceMemoryRepository(sessions)
    assert await repo.find(WORKSPACE, "user-1") is None
    memory = await repo.save(
        UserAIPreferenceMemoryDocument(
            workspace_id=WORKSPACE,
            user_id="user-1",
            entries=[{"id": "e1", "text": "short pages", "source": "manual"}],
        )
    )
    found = await repo.find(WORKSPACE, "user-1")
    assert found.id == memory.id and found.learn_preferences is False
    assert found.entries == [{"id": "e1", "text": "short pages", "source": "manual"}]
    assert await repo.find(WORKSPACE, "user-2") is None
    assert await repo.find(OTHER_WORKSPACE, "user-1") is None

    found.entries.append({"id": "e2", "text": "sentence case", "source": "extracted"})
    found.learn_preferences = True
    found.learn_preferences_at = WHEN
    await repo.save(found)
    again = await repo.find(WORKSPACE, "user-1")
    assert [e["id"] for e in again.entries] == ["e1", "e2"]
    assert again.learn_preferences is True and again.learn_preferences_at == WHEN

    again.entries = []
    again.learn_preferences_at = None
    await repo.save(again)
    cleared = await repo.find(WORKSPACE, "user-1")
    assert cleared.entries == [] and cleared.learn_preferences_at is None

    other = await repo.save(
        UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="user-2")
    )
    assert (await repo.find(WORKSPACE, "user-2")).id == other.id


async def test_one_memory_per_workspace_and_user(sessions):
    repo = PostgresAIPreferenceMemoryRepository(sessions)
    await repo.save(UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u"))
    with pytest.raises(IntegrityError):
        await repo.save(
            UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u")
        )


# -- MCP audit log ---------------------------------------------------------------


async def test_mcp_audit_logs(sessions):
    repo = PostgresMcpAuditLogRepository(sessions)
    assert await repo.list_by_workspace(WORKSPACE) == []
    added = []
    for index, (workspace_id, tool, ok, detail) in enumerate(
        [
            (WORKSPACE, "get_form", True, None),
            (OTHER_WORKSPACE, "list_forms", True, None),
            (WORKSPACE, "apply_ops", False, "validation failed"),
            (WORKSPACE, "list_forms", True, ""),
        ]
    ):
        added.append(
            await repo.add(
                workspace_id=workspace_id,
                key_id="key-1",
                tool=tool,
                ok=ok,
                detail=detail,
                at=WHEN + dt.timedelta(seconds=index),
            )
        )
    listed = await repo.list_by_workspace(WORKSPACE)
    assert [e.id for e in listed] == [added[0].id, added[2].id, added[3].id]
    assert [(e.tool, e.ok, e.detail) for e in listed] == [
        ("get_form", True, None),
        ("apply_ops", False, "validation failed"),
        ("list_forms", True, ""),
    ]
    assert [e.tool for e in await repo.list_by_workspace(str(OTHER_WORKSPACE))] == [
        "list_forms"
    ]
    assert await repo.list_by_workspace(UNKNOWN) == []


async def test_an_mcp_audit_row_is_stored_as_before(sessions):
    """The stored document of an audit entry keeps its 4.0 shape: the
    workspace as an ObjectId, ``at`` and the stamps as ISO strings."""
    repo = PostgresMcpAuditLogRepository(sessions)
    entry = await repo.add(
        workspace_id=WORKSPACE, key_id="key-1", tool="get_form", ok=True, at=WHEN
    )
    async with sessions() as session:
        row = (await session.execute(select(McpAuditLogRow))).scalar_one()
    assert row.id == str(entry.id)
    assert row.workspace_id == str(WORKSPACE)
    assert row.doc["_id"] == {"$oid": str(entry.id)}
    assert row.doc["workspace_id"] == {"$oid": str(WORKSPACE)}
    assert row.doc["at"] == WHEN.isoformat()
    assert {k: row.doc[k] for k in ("key_id", "tool", "ok", "detail")} == {
        "key_id": "key-1",
        "tool": "get_form",
        "ok": True,
        "detail": None,
    }
    assert set(row.doc) == {
        "_id",
        "created_at",
        "updated_at",
        "workspace_id",
        "key_id",
        "tool",
        "ok",
        "detail",
        "at",
    }


# -- form prompts ----------------------------------------------------------------


async def test_create_form_prompts(sessions):
    repo = PostgresCreateFormPromptRepository(sessions)
    form_id, other = RecordId(), RecordId()

    def prompt(text):
        return CreateFormPrompt(
            prompt=text,
            openai_response={"title": "Outline", "sections": [{"title": "One"}]},
            created_form={"title": "Form", "fields": []},
            form_id=form_id,
        )

    assert await repo.list_by_form_id(form_id) == []
    first = await repo.add(prompt("a survey"))
    await repo.add(prompt("a survey, again"))
    assert first.id is not None
    listed = await repo.list_by_form_id(form_id)
    assert [p.prompt for p in listed] == ["a survey", "a survey, again"]
    assert listed[0].id == first.id and listed[0].form_id == form_id
    assert listed[0].openai_response == {
        "title": "Outline",
        "sections": [{"title": "One"}],
    }
    assert [p.prompt for p in await repo.list_by_form_id(str(form_id))] == [
        "a survey",
        "a survey, again",
    ]
    assert await repo.list_by_form_id(other) == []


# -- Idempotency-Key records -----------------------------------------------------


def _record(record_id: str, minutes: int = 60, request_hash: str = "h1"):
    return ApiIdempotencyRecordDocument(
        id=RecordId(record_id),
        key_id="k" * 24,
        request_hash=request_hash,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes),
    )


async def test_claim_once_then_complete_and_find(sessions):
    repo = PostgresIdempotencyRepository(sessions)
    record_id = "a" * 24
    assert await repo.find(record_id) is None
    assert await repo.claim(_record(record_id)) is True
    assert await repo.claim(_record(record_id, request_hash="h2")) is False
    found = await repo.find(record_id)
    assert (found.state, found.request_hash) == ("pending", "h1")
    await repo.complete(record_id, 201, '{"ok": true}', '"etag-1"')
    found = await repo.find(record_id)
    assert (found.state, found.status_code, found.body, found.etag) == (
        "done",
        201,
        '{"ok": true}',
        '"etag-1"',
    )
    # a second completion keeps the first response
    await repo.complete(record_id, 500, "{}", None)
    assert (await repo.find(record_id)).status_code == 201
    # a release only drops an unfinished claim
    await repo.release(record_id)
    assert (await repo.find(record_id)).state == "done"


async def test_release_lets_a_retry_claim_again(sessions):
    repo = PostgresIdempotencyRepository(sessions)
    record_id = "b" * 24
    assert await repo.claim(_record(record_id)) is True
    await repo.release(record_id)
    assert await repo.find(record_id) is None
    assert await repo.claim(_record(record_id)) is True


async def test_an_expired_record_is_not_found_and_gives_way(sessions):
    repo = PostgresIdempotencyRepository(sessions)
    record_id = "c" * 24
    assert await repo.claim(_record(record_id, minutes=-1)) is True
    assert await repo.find(record_id) is None
    assert await repo.claim(_record(record_id, request_hash="new")) is True
    assert (await repo.find(record_id)).request_hash == "new"


async def test_concurrent_claims_have_one_winner(sessions):
    repo = PostgresIdempotencyRepository(sessions)
    record_id = "d" * 24
    won = await asyncio.gather(*(repo.claim(_record(record_id)) for _ in range(8)))
    assert sorted(won) == [False] * 7 + [True]


async def test_expired_records_are_dropped(sessions):
    repo = PostgresIdempotencyRepository(sessions)
    await repo.claim(_record("e" * 24, minutes=-1))
    await repo.claim(_record("f" * 24))  # a new record sweeps expired ones
    async with sessions() as session:
        ids = (await session.execute(select(ApiIdempotencyKeyRow.id))).scalars().all()
    assert ids == ["f" * 24]
