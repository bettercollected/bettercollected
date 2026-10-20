"""The Postgres twins of the ai-group repositories behave like the Mongo originals.

Every public method of the insight, session, profile, preference-memory and MCP
audit repositories runs on both stores with the same inputs; results and the
stored documents are compared (ids as labels, timestamps aside). The
idempotency records have their own test. Skipped unless DATABASE_URL points at
a *_test database.
"""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from pymongo.errors import DuplicateKeyError
from sqlalchemy.exc import IntegrityError

from backend.app.container import container
from backend.app.repositories.ai_preference_memory_repository import (
    AIPreferenceMemoryRepository,
)
from backend.app.repositories.form_ai_insight_repository import FormAIInsightRepository
from backend.app.repositories.form_ai_session_repository import FormAISessionRepository
from backend.app.repositories.mcp_audit_log_repository import McpAuditLogRepository
from backend.app.repositories.postgres.ai import (
    PostgresAIPreferenceMemoryRepository,
    PostgresFormAIInsightRepository,
    PostgresFormAISessionRepository,
    PostgresMcpAuditLogRepository,
    PostgresWorkspaceAIProfileRepository,
)
from backend.app.repositories.workspace_ai_profile_repository import (
    WorkspaceAIProfileRepository,
)
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.db.models import (
    AiPreferenceMemoryRow,
    FormAiInsightRow,
    FormAiSessionRow,
    McpAuditLogRow,
    WorkspaceAiProfileRow,
)
from common.exceptions import NotFoundError
from tests.app.repositories.parity_helpers import run_on_both

WORKSPACE = PydanticObjectId("65f0a1b2c3d4e5f600000001")
OTHER_WORKSPACE = PydanticObjectId("65f0a1b2c3d4e5f600000002")
UNKNOWN = PydanticObjectId("65f0a1b2c3d4e5f6000000ff")
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


async def insights_scenario(repo, ids, record):
    record.append(await repo.find(WORKSPACE, "form-1"))
    first = await repo.save(_insight("form-1"))
    ids.label(first.id, "first")
    record.append(first)
    record.append(await repo.find(WORKSPACE, "form-1"))
    record.append(await repo.find(OTHER_WORKSPACE, "form-1"))
    record.append(await repo.find(WORKSPACE, "form-2"))
    # regenerated: the same document, replaced
    first.payload = {"summary": "again", "nested": {"none": None, "list": []}}
    first.response_count = 4
    record.append(await repo.save(first))
    record.append(await repo.find(WORKSPACE, "form-1"))
    other = await repo.save(_insight("form-1", OTHER_WORKSPACE, extra=True))
    ids.label(other.id, "other")
    record.append(await repo.find(OTHER_WORKSPACE, "form-1"))
    record.append(await repo.find(WORKSPACE, "form-1"))


async def test_form_ai_insights(sessions):
    await run_on_both(
        insights_scenario,
        FormAIInsightRepository(),
        PostgresFormAIInsightRepository(sessions),
        stored=[(FormAIInsightDocument, FormAiInsightRow)],
        sessions=sessions,
    )


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


async def _not_found(call):
    try:
        await call
    except NotFoundError as error:
        return f"NotFoundError: {error}"
    return "no error"


async def sessions_scenario(repo, ids, record):
    record.append(await _not_found(repo.get_or_404(UNKNOWN)))
    chat = await repo.save(
        _session({"id": "p1", "status": "pending"}, {"id": "p2", "status": "pending"})
    )
    ids.label(chat.id, "chat")
    record.append(chat)
    record.append(await repo.get_or_404(chat.id))

    update = repo.update_proposal
    record.append(await update(chat.id, "p1", {"status": "applied", "at": "t1"}))
    # only while the proposal still has the expected status
    record.append(await update(chat.id, "p1", {"status": "rejected"}, "pending"))
    record.append(await update(chat.id, "p2", {"status": "rejected"}, "pending"))
    # a new key, and nothing else of the message changes
    record.append(await update(chat.id, "p2", {"attempt": 2}))
    # setting what is already there changes nothing: not an update
    record.append(await update(chat.id, "p1", {"status": "applied", "at": "t1"}))
    record.append(await update(chat.id, "missing", {"status": "x"}))
    record.append(await update(UNKNOWN, "p1", {"status": "x"}))
    record.append(await repo.get_or_404(chat.id))

    # a chat turn saves the whole session (and keeps the decisions it read)
    turn = await repo.get_or_404(chat.id)
    turn.messages.append({"role": "user", "content": "thanks", "none": None})
    record.append(await repo.save(turn))
    record.append(await repo.get_or_404(chat.id))

    # every record carrying the id is matched, each against the status filter
    twice = await repo.save(
        _session(
            {"id": "dup", "status": "pending"},
            {"id": "dup", "status": "applied"},
            form_id="form-2",
        )
    )
    ids.label(twice.id, "twice")
    record.append(await update(twice.id, "dup", {"status": "seen"}, "applied"))
    record.append(await repo.get_or_404(twice.id))
    record.append(await update(twice.id, "dup", {"note": "both"}))
    record.append(await repo.get_or_404(twice.id))


async def test_form_ai_sessions(sessions):
    await run_on_both(
        sessions_scenario,
        FormAISessionRepository(),
        PostgresFormAISessionRepository(sessions),
        stored=[(FormAISessionDocument, FormAiSessionRow)],
        sessions=sessions,
    )


# -- workspace AI profiles -------------------------------------------------------


async def profiles_scenario(repo, ids, record):
    record.append(await repo.find_by_workspace(WORKSPACE))
    profile = await repo.save(
        WorkspaceAIProfileDocument(workspace_id=WORKSPACE, about="We are kind.")
    )
    ids.label(profile.id, "profile")
    record.append(profile)
    record.append(await repo.find_by_workspace(WORKSPACE))
    record.append(await repo.find_by_workspace(OTHER_WORKSPACE))
    profile.guidelines = "Short questions."
    profile.compliance = "No health data."
    profile.updated_by = "user-1"
    profile.revisions = [{"about": "We are kind.", "at": WHEN.isoformat(), "by": None}]
    record.append(await repo.save(profile))
    record.append(await repo.find_by_workspace(WORKSPACE))
    other = await repo.save(WorkspaceAIProfileDocument(workspace_id=OTHER_WORKSPACE))
    ids.label(other.id, "other")
    record.append(await repo.find_by_workspace(OTHER_WORKSPACE))


async def test_workspace_ai_profiles(sessions):
    await run_on_both(
        profiles_scenario,
        WorkspaceAIProfileRepository(),
        PostgresWorkspaceAIProfileRepository(sessions),
        stored=[(WorkspaceAIProfileDocument, WorkspaceAiProfileRow)],
        sessions=sessions,
    )


async def test_one_profile_per_workspace_in_both_stores(sessions):
    for repo, refused in (
        (WorkspaceAIProfileRepository(), DuplicateKeyError),
        (PostgresWorkspaceAIProfileRepository(sessions), IntegrityError),
    ):
        await repo.save(WorkspaceAIProfileDocument(workspace_id=WORKSPACE))
        with pytest.raises(refused):
            await repo.save(WorkspaceAIProfileDocument(workspace_id=WORKSPACE))


# -- AI preference memories ------------------------------------------------------


async def memories_scenario(repo, ids, record):
    record.append(await repo.find(WORKSPACE, "user-1"))
    memory = await repo.save(
        UserAIPreferenceMemoryDocument(
            workspace_id=WORKSPACE,
            user_id="user-1",
            entries=[{"id": "e1", "text": "short pages", "source": "manual"}],
        )
    )
    ids.label(memory.id, "memory")
    record.append(memory)
    record.append(await repo.find(WORKSPACE, "user-1"))
    record.append(await repo.find(WORKSPACE, "user-2"))
    record.append(await repo.find(OTHER_WORKSPACE, "user-1"))
    memory.entries.append({"id": "e2", "text": "sentence case", "source": "extracted"})
    memory.learn_preferences = True
    memory.learn_preferences_at = WHEN
    record.append(await repo.save(memory))
    record.append(await repo.find(WORKSPACE, "user-1"))
    memory.entries = []
    memory.learn_preferences_at = None
    record.append(await repo.save(memory))
    record.append(await repo.find(WORKSPACE, "user-1"))
    other = await repo.save(
        UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="user-2")
    )
    ids.label(other.id, "other")
    record.append(await repo.find(WORKSPACE, "user-2"))


async def test_ai_preference_memories(sessions):
    await run_on_both(
        memories_scenario,
        AIPreferenceMemoryRepository(),
        PostgresAIPreferenceMemoryRepository(sessions),
        stored=[(UserAIPreferenceMemoryDocument, AiPreferenceMemoryRow)],
        sessions=sessions,
    )


async def test_one_memory_per_workspace_and_user_in_postgres(sessions):
    repo = PostgresAIPreferenceMemoryRepository(sessions)
    await repo.save(UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u"))
    with pytest.raises(IntegrityError):
        await repo.save(
            UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u")
        )


async def test_one_memory_per_workspace_and_user_in_mongo(sessions):
    repo = AIPreferenceMemoryRepository()
    await repo.save(UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u"))
    with pytest.raises(DuplicateKeyError):
        await repo.save(
            UserAIPreferenceMemoryDocument(workspace_id=WORKSPACE, user_id="u")
        )


# -- MCP audit log ---------------------------------------------------------------


async def audit_scenario(repo, ids, record):
    record.append(await repo.list_by_workspace(WORKSPACE))
    for index, (workspace_id, tool, ok, detail) in enumerate(
        [
            (WORKSPACE, "get_form", True, None),
            (OTHER_WORKSPACE, "list_forms", True, None),
            (WORKSPACE, "apply_ops", False, "validation failed"),
            (WORKSPACE, "list_forms", True, ""),
        ]
    ):
        entry = await repo.add(
            workspace_id=workspace_id,
            key_id="key-1",
            tool=tool,
            ok=ok,
            detail=detail,
            at=WHEN + dt.timedelta(seconds=index),
        )
        ids.label(entry.id, f"entry{index}")
        record.append(entry)
    record.append(await repo.list_by_workspace(WORKSPACE))
    record.append(await repo.list_by_workspace(OTHER_WORKSPACE))
    record.append(await repo.list_by_workspace(UNKNOWN))


async def test_mcp_audit_logs(sessions):
    await run_on_both(
        audit_scenario,
        McpAuditLogRepository(),
        PostgresMcpAuditLogRepository(sessions),
        stored=[(MCPAuditLogDocument, McpAuditLogRow)],
        sessions=sessions,
    )
