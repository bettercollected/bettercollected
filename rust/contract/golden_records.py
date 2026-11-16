"""Golden vectors for the Rust record layer (`bc-db`): rows the Python backend writes.

    uv run --project backend python rust/contract/golden_records.py migrate
    uv run --project backend python rust/contract/golden_records.py generate rust/bc-db/tests/golden/records.json

Needs DATABASE_URL naming a throw-away database whose name contains "test" (the
CI backend-tests environment otherwise). `migrate` brings it to the Alembic head.
`generate` builds records with the real Python document classes (a workspace, a
member, a form, a response without encrypted fields, an audit entry), writes
each one through the repository code the application uses (`RecordRepository`
upsert), reads the row back and records, per case:

* `input`   the JSON the Rust test builds its typed record from;
* `row`     the whole stored row as `to_jsonb` of it: `doc`, `created_at`,
            `updated_at`, `_bc_source`, `_bc_checksum` and every generated spine
            column (the session time zone is UTC);
* `now`     the instant the clock stood at for the case (a case without
            timestamps is stamped with it).

It also records `read_cases` (stored documents Python reads, with what it writes
back, or that it refuses them), and the ids and lock keys Python derives.
Nothing here holds a real key or real data.
"""

import asyncio
import datetime as dt
import hashlib
import json
import os
import sys
import types
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "common"), str(ROOT / "backend")]
# importing anything under backend.app runs its __init__, which boots the whole
# application: register the packages without running it
for _name, _path in (("backend", "backend/backend"), ("backend.app", "backend/backend/app")):
    _m = types.ModuleType(_name)
    _m.__path__ = [str(ROOT / _path)]
    sys.modules[_name] = _m

NOW = dt.datetime(2026, 5, 6, 7, 8, 9, 123456, tzinfo=dt.timezone.utc)
WS = "6a0000000000000000000001"
USER = "6a0000000000000000000002"
USER2 = "6a0000000000000000000003"


def ids(n):
    return "6a00000000000000000a%04d" % n


TS1 = "2026-01-02T03:04:05.678901+00:00"
TS2 = "2026-02-03T04:05:06+00:00"
TSZ = "2026-03-04T05:06:07.891234+02:00"
TSN = "2026-03-04T05:06:07.891234"
TEXT = 'tëxt ✓ "quoted" \\ line\nbreak \u0001   日本語'


def cases():
    """(table, name, input) in the document's stored shape; `_id` always set."""
    out = []

    def add(table, name, doc):
        out.append({"table": table, "name": name, "input": doc})

    # workspaces
    add("workspaces", "minimal", {"_id": ids(1), "workspace_name": "ws-minimal", "created_at": TS1, "updated_at": TS1})
    add("workspaces", "stamped by the clock", {"_id": ids(2), "workspace_name": "ws-stamped"})
    add(
        "workspaces",
        "full",
        {
            "_id": ids(3),
            "created_at": TS1,
            "updated_at": TS2,
            "title": TEXT,
            "workspace_name": "ws-full",
            "description": "d",
            "profile_image": "https://img.example.test/p.png",
            "banner_image": None,
            "custom_domain": "forms.example.test",
            "privacy_policy": "https://example.test/privacy",
            "terms_of_service": None,
            "custom_themes": [{"title": "T", "primary": "#000000", "secondary": "#111111", "tertiary": "#222222", "accent": "#333333", "background": None, "style": None}],
            "is_pro": True,
            "custom_domain_id": "dom-1",
            "custom_domain_status": "ready",
            "custom_domain_dns_records": [{"type": "CNAME", "name": "forms", "value": "x.example.test"}],
            "custom_domain_checks": [{"name": "dns", "ok": True}],
            "custom_domain_updated_at": TSZ,
            "ai_enabled": True,
            "ai_provider": "openai",
            "ai_enabled_by": USER,
            "ai_enabled_at": TS2,
            "sso_required": True,
            "sso_required_changed_by": USER,
            "sso_required_changed_at": TSN,
            "sso_default_role": "VIEWER",
            "require_totp": True,
            "audit_retention_months": 24,
            "embed_allowed_origins": ["https://a.example.test", "https://b.example.test"],
            "captcha_default": False,
            "app_theme": "pigment",
            "owner_id": USER,
            "default": True,
            "custom_domain_disabled": False,
            "custom_domain_verified": True,
            "disabled": False,
        },
    )
    # members
    add("workspace_users", "minimal", {"_id": ids(10), "workspace_id": WS, "user_id": USER, "created_at": TS1, "updated_at": TS1})
    add(
        "workspace_users",
        "roles and reasons",
        {
            "_id": ids(11),
            "workspace_id": WS,
            "user_id": USER2,
            "roles": ["ADMIN", "EDITOR", "a role from the future"],
            "disabled": True,
            "provisioned_by": "scim",
            "disabled_reasons": ["directory", "plan"],
            "created_at": TS2,
            "updated_at": TSZ,
        },
    )
    # forms
    add("forms", "minimal", {"_id": ids(20), "form_id": "form-min", "title": "T", "created_at": TS1, "updated_at": TS1})
    add(
        "forms",
        "full",
        {
            "_id": ids(21),
            "created_at": TS1,
            "updated_at": TS2,
            "builder_version": "v2",
            "form_id": "form-full",
            "imported_form_id": None,
            "type": "standard",
            "title": TEXT,
            "logo": None,
            "logo_position": "left",
            "logo_alt": "alt",
            "use_workspace_logo": False,
            "cover_image": None,
            "description": "desc",
            "button_text": "Send",
            "is_multi_page": True,
            "fields": [
                {"id": "f1", "title": "Name", "type": "short_text", "required": True, "properties": {"placeholder": None, "maxLength": 12.5, "scale": 1e16, "big": 9007199254740993}},
            ],
            "hidden_fields": ["utm_source"],
            "consent": None,
            "state": {"global_state": {"a": 1}, "processor_state": None, "is_locked": True},
            "settings": {"embed_url": None, "custom_url": "my-form", "provider": "self", "language": "nl", "is_public": True, "is_trial": False, "response_data_owner_field": None, "response_data_owner_fields": None, "screens": None, "privacy_policy_url": None, "response_expiration": None, "response_expiration_type": None, "is_response_editable": None, "is_closed": False},
            "published_at": TSZ,
            "actions": None,
            "parameters": None,
            "secrets": None,
            "theme": None,
            "welcome_page": None,
            "thankyou_page": None,
            "row_titles": None,
            "column_titles": ["x", "y"],
        },
    )
    # responses (no encrypted fields)
    add(
        "form_responses",
        "minimal",
        {"_id": ids(30), "form_id": "form-full", "response_id": "resp-1", "workspace_id": WS, "created_at": TS1, "updated_at": TS1},
    )
    add(
        "form_responses",
        "metadata",
        {
            "_id": ids(31),
            "form_id": "form-full",
            "response_id": "resp-2",
            "provider": "self",
            "respondent_email": None,
            "internal_answers_version": 3,
            "form_version": 2,
            "published_at": TSN,
            "expiration": "2027-01-01",
            "expiration_type": "date",
            "dataOwnerIdentifier": "owner-1",
            "dataOwnerIdentifierType": "email",
            "anonymous_identity": "v2:abc",
            "submission_uuid": "11111111-2222-3333-4444-555555555555",
            "ai_notice_shown_at": TS2,
            "ai_notice_provider_name": "openai",
            "shared_as_choices": ["f1"],
            "ending_id": "end-1",
            "workspace_id": WS,
            "created_at": TS2,
            "updated_at": TSZ,
        },
    )
    # audit entries
    add(
        "workspace_audit_events",
        "request entry",
        {"_id": ids(40), "workspace_id": WS, "user_id": USER, "session_id": "sess-1", "event": "sso_break_glass_request", "method": "GET", "path": "/workspaces/{workspace_id}/forms", "created_at": TS1, "updated_at": TS1},
    )
    add(
        "workspace_audit_events",
        "member event",
        {
            "_id": ids(41),
            "workspace_id": WS,
            "user_id": USER,
            "event": "member_role_changed",
            "target_user_id": USER2,
            "role": "ADMIN",
            "previous_role": "EDITOR",
            "count": 2,
            "widened": True,
            "changed": ["name", "fields"],
            "export_filters": None,
            "retention_months": 12,
            "created_at": TSZ,
            "updated_at": TSZ,
        },
    )
    return out


# stored documents Python reads: what it writes back, or that it refuses
READ_CASES = [
    ("workspaces", "old workspace without newer keys", {"_id": {"$oid": ids(50)}, "workspace_name": "old", "created_at": TS1}),
    ("workspaces", "unknown keys are dropped", {"_id": {"$oid": ids(51)}, "workspace_name": "x", "gone": [1, 2], "created_at": TS1, "updated_at": TS1}),
    ("workspaces", "lax bool spellings", {"_id": {"$oid": ids(52)}, "workspace_name": "x", "default": "true", "disabled": 1, "ai_enabled": "false", "created_at": TS1, "updated_at": TS1}),
    ("workspaces", "plain string id and BSON dates", {"_id": ids(53), "workspace_name": "x", "created_at": {"$date": "2026-01-02T03:04:05.678Z"}, "updated_at": {"$date": {"$numberLong": "1767323045678"}}}),
    ("workspaces", "no timestamps", {"_id": {"$oid": ids(54)}, "workspace_name": "x"}),
    ("workspaces", "zulu, space, compact offset and date-only", {"_id": {"$oid": ids(55)}, "workspace_name": "x", "created_at": "2026-01-02T03:04:05Z", "updated_at": "2026-01-02 03:04:05+0200", "ai_enabled_at": "2026-01-02", "sso_required_changed_at": "2026-01-02T03:04:05.1234567"}),
    ("workspaces", "explicit nulls stay null", {"_id": {"$oid": ids(56)}, "workspace_name": "x", "ai_enabled": None, "disabled": None, "created_at": TS1, "updated_at": TS1}),
    ("workspaces", "name missing is refused", {"_id": {"$oid": ids(57)}, "created_at": TS1}),
    ("workspaces", "name not a string is refused", {"_id": {"$oid": ids(58)}, "workspace_name": 5, "created_at": TS1}),
    ("workspaces", "bad bool is refused", {"_id": {"$oid": ids(59)}, "workspace_name": "x", "default": "maybe"}),
    ("workspaces", "retention as text", {"_id": {"$oid": ids(60)}, "workspace_name": "x", "audit_retention_months": "12", "created_at": TS1, "updated_at": TS1}),
    ("workspace_users", "old membership without roles", {"_id": {"$oid": ids(61)}, "workspace_id": {"$oid": WS}, "user_id": {"$oid": USER}, "created_at": TS1, "updated_at": TS1}),
    ("workspace_users", "ids as plain strings", {"_id": ids(62), "workspace_id": WS, "user_id": USER, "roles": ["OWNER"], "created_at": TS1, "updated_at": TS1}),
    ("workspace_users", "a number in roles is refused", {"_id": {"$oid": ids(63)}, "workspace_id": {"$oid": WS}, "user_id": {"$oid": USER}, "roles": ["ADMIN", 5]}),
    ("workspace_users", "malformed user id is refused", {"_id": {"$oid": ids(64)}, "workspace_id": {"$oid": WS}, "user_id": "nope"}),
    ("forms", "defaults for state and settings", {"_id": {"$oid": ids(65)}, "form_id": "f", "created_at": TS1, "updated_at": TS1}),
    ("forms", "null settings stays null", {"_id": {"$oid": ids(66)}, "form_id": "f", "settings": None, "state": None, "created_at": TS1, "updated_at": TS1}),
    ("form_responses", "old response without a workspace", {"_id": {"$oid": ids(67)}, "form_id": "f", "response_id": "r", "created_at": TS1, "updated_at": TS1}),
    ("form_responses", "version as text", {"_id": {"$oid": ids(68)}, "form_id": "f", "form_version": "3", "created_at": TS1, "updated_at": TS1}),
    ("workspace_audit_events", "revision as text", {"_id": {"$oid": ids(69)}, "workspace_id": {"$oid": WS}, "user_id": "u", "event": "e", "revision": "3", "created_at": TS1, "updated_at": TS1}),
    ("workspace_audit_events", "event missing is refused", {"_id": {"$oid": ids(70)}, "workspace_id": {"$oid": WS}, "user_id": "u"}),
]


# Parts of a document that are models of their own (a form's fields, a theme). The
# Rust record carries them as JSON in document form, so the vector's input holds
# them as Python normalises them (every optional key present); the typed top level
# is left as the case wrote it.
OPAQUE = {
    "workspaces": ("custom_themes", "custom_domain_dns_records", "custom_domain_checks"),
    "forms": ("fields", "consent", "theme", "welcome_page", "thankyou_page", "actions", "parameters", "secrets"),
    "form_responses": ("answers", "hidden_fields", "internal_answers", "internal_answers_meta", "respondent_feedback", "consent", "state", "submission_source"),
}


# Every spelling of a flag and of an integer the Python models are asked to read:
# Python says which it takes (and what it writes back) and which it refuses.
BOOL_SPELLINGS = [True, False, 0, 1, 2, -1, 0.0, 1.0, -0.0, 0.5, 2.0, "true", "True", "TRUE", " true", "true ", "t", "T", "yes", "Y", "on", "ON", "off", "no", "n", "f", "false", "0", "1", "2", "", "maybe", "1.0", "0.0", None, [], {}]
INT_SPELLINGS = [7, "7", " 7 ", "7.0", 7.0, 7.5, "abc", "", True, False, "+7", "-7", "1e2", None, [], 0, -1]


def _spelling_cases():
    n = 100
    out = []
    for value in BOOL_SPELLINGS:
        n += 1
        out.append(("workspaces", f"flag disabled = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_name": "x", "disabled": value, "created_at": TS1, "updated_at": TS1}))
        n += 1
        out.append(("workspaces", f"flag require_totp = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_name": "x", "require_totp": value, "created_at": TS1, "updated_at": TS1}))
        n += 1
        out.append(("workspaces", f"flag sso_required = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_name": "x", "sso_required": value, "created_at": TS1, "updated_at": TS1}))
        n += 1
        out.append(("workspaces", f"bool default = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_name": "x", "default": value, "created_at": TS1, "updated_at": TS1}))
        n += 1
        out.append(("workspace_users", f"bool disabled = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_id": {"$oid": WS}, "user_id": {"$oid": USER}, "disabled": value, "created_at": TS1, "updated_at": TS1}))
    for value in INT_SPELLINGS:
        n += 1
        out.append(("workspaces", f"int audit_retention_months = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_name": "x", "audit_retention_months": value, "created_at": TS1, "updated_at": TS1}))
        n += 1
        out.append(("workspace_audit_events", f"int revision = {json.dumps(value)}", {"_id": {"$oid": ids(n)}, "workspace_id": {"$oid": WS}, "user_id": "u", "event": "e", "revision": value, "created_at": TS1, "updated_at": TS1}))
    return out


READ_CASES += _spelling_cases()


def classes():
    from backend.app.schemas.workspace import WorkspaceDocument
    from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
    from backend.app.schemas.workspace_form import WorkspaceFormDocument  # noqa: F401  (imported for the key check)
    from backend.app.schemas.workspace_user import WorkspaceUserDocument
    from backend.app.schemas.standard_form import FormDocument
    from backend.app.schemas.standard_form_response import FormResponseDocument
    from backend.db import models

    return {
        "workspaces": (WorkspaceDocument, models.WorkspaceRow),
        "workspace_users": (WorkspaceUserDocument, models.WorkspaceUserRow),
        "forms": (FormDocument, models.FormRow),
        "form_responses": (FormResponseDocument, models.FormResponseRow),
        "workspace_audit_events": (WorkspaceAuditEventDocument, models.WorkspaceAuditEventRow),
    }


def migrate():
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(config, "head")
    print("migrated")


async def generate(path):
    from sqlalchemy import text

    from common.db.engine import DatabaseSettings, make_engine, make_sessionmaker
    from common.records.codec import decode, encode, row_values
    from common.records.repository import RecordRepository

    url = os.environ["DATABASE_URL"]
    if "test" not in url.rsplit("/", 1)[-1]:
        raise SystemExit("DATABASE_URL must name a database with 'test' in its name")
    engine = make_engine(DatabaseSettings.from_env(), application_name="golden-records")
    sessions = make_sessionmaker(engine)
    kinds = classes()
    out = {"now": NOW.isoformat(), "cases": [], "read_cases": [], "derived_ids": [], "advisory_keys": []}

    async def fetch(table, row_id):
        async with sessions() as session, session.begin():
            await session.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            return (
                await session.execute(text(f"SELECT to_jsonb(t.*) FROM app.{table} t WHERE id = :i"), {"i": row_id})
            ).scalar_one()

    with mock.patch("common.records.base.utcnow", lambda: NOW):
        for case in cases():
            table, doc_cls, row_cls = case["table"], *kinds[case["table"]]
            normal = encode(doc_cls(**case["input"]))
            for key in OPAQUE.get(table, ()):
                if key in case["input"]:
                    case["input"][key] = normal[key]
            record = doc_cls(**case["input"])
            repo = type("Repo", (RecordRepository,), {"row": row_cls, "document": doc_cls})(sessions)
            async with sessions() as session, session.begin():
                await session.execute(text(f"DELETE FROM app.{table} WHERE id = :i"), {"i": case["input"]["_id"]})
            await repo.upsert(record)
            case["row"] = await fetch(table, case["input"]["_id"])
            assert case["row"]["_bc_checksum"] == row_values(record)["bc_checksum"]
            out["cases"].append(case)

        for table, name, stored in READ_CASES:
            doc_cls, _ = kinds[table]
            entry = {"table": table, "name": name, "stored": stored}
            try:
                entry["rewritten"] = encode(decode(doc_cls, stored))
            except Exception as error:  # noqa: BLE001 - the vector says "refused"
                entry["refused"] = type(error).__name__
            out["read_cases"].append(entry)

    from common.ids import derived_id

    for parts in (["a", "b"], ["workspace", WS, "user", USER], ["x"], ["é", "日本"]):
        out["derived_ids"].append({"parts": parts, "id": str(derived_id(*parts))})
        digest = hashlib.sha1("\x00".join(parts).encode()).digest()
        out["advisory_keys"].append({"parts": parts, "key": int.from_bytes(digest[:8], "big", signed=True)})
    out["python_model_keys"] = {t: sorted((c.model_fields[k].alias or k) for k in c.model_fields) for t, (c, _) in kinds.items()}
    await engine.dispose()
    Path(path).write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(out['cases'])} cases and {len(out['read_cases'])} read cases to {path}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "migrate":
        migrate()
    elif command == "generate" and len(sys.argv) == 3:
        asyncio.run(generate(sys.argv[2]))
    else:
        raise SystemExit(__doc__)
