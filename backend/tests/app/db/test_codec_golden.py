"""Golden fixtures of the ``doc`` codec for every backend document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``.
"""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select

from backend.app.container import container
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.allowed_origin import AllowedOriginsDocument
from backend.app.schemas.api_idempotency_record import ApiIdempotencyRecordDocument
from backend.app.schemas.coupon_codes import CouponCodeDocument
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.form_ai_insight import FormAIInsightDocument
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.price_suggestion import PriceSuggestion
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from backend.app.schemas.user_feedback import UserFeedbackDocument
from backend.app.schemas.workspace_ai_profile import WorkspaceAIProfileDocument
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
)
from backend.app.schemas.session import SessionDocument
from backend.app.schemas.sso_connection import SsoConnectionDocument
from backend.app.schemas.sso_used_state import SsoUsedStateDocument
from backend.app.schemas.user_tags import UserTagsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_domain import WorkspaceDomainDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.schemas.consent import WorkspaceConsentDocument
from backend.app.schemas.form_import import FormImportDocument
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.media_library import MediaLibraryDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupFormDocument,
    ResponderGroupMemberDocument,
)
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_responder import (
    WorkspaceResponderDocument,
    WorkspaceTags,
)
from backend.db.base import Base
from common.db import BaseRow, canonical_json, checksum
from common.records.repository import RecordRepository
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    load,
    mirrored_documents,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "codec_golden" / "backend.json"

# Tables written only by the migration (raw documents, no Beanie class); their
# codec path is covered by common/tests/test_codec_golden.py. Also the tables
# that exist only in Postgres (new in 4.2, registration): they were never in
# Mongo, so there are no 4.0 bytes to pin and no Beanie original to compare.
NO_DOCUMENT_CLASS = {
    "scheduler_form_configs",
    "registration_services",
    "form_registrations",
    "registration_deliveries",
}

# The document classes, all on ``Record`` (every group is served from Postgres
# only). The 4.0 Beanie classes they replaced are frozen in
# tests/app/db/beanie_originals.py.
RECORD_CLASSES = (
    AllowedOriginsDocument,
    FormPluginConfigDocument,
    CouponCodeDocument,
    PriceSuggestion,
    UserFeedbackDocument,
    FlowEventDocument,
    RateLimitCounterDocument,
    UserAIPreferenceMemoryDocument,
    FormAISessionDocument,
    FormAIInsightDocument,
    WorkspaceAIProfileDocument,
    MCPAuditLogDocument,
    CreateFormPrompt,
    ApiIdempotencyRecordDocument,
    ActionDocument,
    WorkspaceActionsDocument,
    WorkspaceDocument,
    WorkspaceUserDocument,
    WorkspaceUserInvitesDocument,
    WorkspaceAPIKeyDocument,
    WorkspaceDomainDocument,
    SsoConnectionDocument,
    SsoUsedStateDocument,
    ScimDirectoryDocument,
    ScimUserDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimEventDocument,
    BlackListedRefreshTokens,
    SessionDocument,
    UserTagsDocument,
    FormDocument,
    FormVersionsDocument,
    FormTemplateDocument,
    WorkspaceFormDocument,
    FormImportDocument,
    MediaLibraryDocument,
    WorkspaceConsentDocument,
    FormResponseDocument,
    FormResponseDeletionRequest,
    WorkspaceTags,
    WorkspaceResponderDocument,
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
)

# Values the synthesizer cannot guess (a field validator with a checksum).
OVERRIDES = {"coupon_codes": {"code": "A" * 24 + "0"}}


def _rows():
    return [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]


def _models():
    return list(RECORD_CLASSES)


def _documents():
    return mirrored_documents(_rows(), _models())


def test_every_mirrored_table_has_a_document_class_or_is_listed(_initialized_app):
    missing = sorted(c for c, cls in _documents().items() if cls is None)
    assert missing == sorted(NO_DOCUMENT_CLASS)


def test_encoding_matches_the_pinned_bytes(_initialized_app):
    documents = {c: cls for c, cls in _documents().items() if cls is not None}
    assert check(FIXTURE, build_cases(documents, OVERRIDES)) == []


def test_decode_then_encode_gives_the_pinned_bytes(_initialized_app):
    classes = {cls.__name__: cls for cls in _models()}
    assert check_round_trip(FIXTURE, classes) == []


async def test_postgres_stores_and_returns_the_pinned_bytes(clean_postgres):
    """JSONB keeps every pinned value (large integers, floats, Extended JSON tags)."""
    tables = {row.mongo_collection(): row for row in _rows()}
    store = RecordRepository(container.pg_sessionmaker())
    now = datetime.now(timezone.utc)
    problems = []
    for name, case in sorted(load(FIXTURE).items()):
        row = tables[name.split("/")[0]]
        row_id = case["doc"]["_id"]["$oid"]
        values = {
            "id": row_id,
            "doc": case["doc"],
            "created_at": now,
            "updated_at": now,
            "bc_source": "app",
            "bc_checksum": case["checksum"],
        }
        async with store._session() as session, session.begin():
            await session.execute(store._upsert_statement(values, row))
        async with store._session() as session:
            stored = (
                await session.execute(
                    select(row.doc, row.bc_checksum).where(row.id == row_id)
                )
            ).one()
        async with store._session() as session, session.begin():
            await session.execute(delete(row).where(row.id == row_id))
        if canonical_json(stored.doc) != canonical_json(case["doc"]):
            problems.append(f"{name}: doc changed in Postgres")
        if case["checksum"] != checksum(stored.doc) or (
            case["checksum"] != stored.bc_checksum
        ):
            problems.append(f"{name}: checksum changed in Postgres")
    assert problems == []
