"""Seed a throw-away database through the Python backend's own code.

    uv run --project backend python rust/contract/seed.py migrate
    uv run --project backend python rust/contract/seed.py seed <fixture.json>

``migrate`` brings the database to the Alembic head and applies the job queue
schema (what the test-suite's session fixture does). ``seed`` creates the
workspaces, members and tokens the contract test sends, and writes them (ids
and tokens, which are throw-away) to the fixture file. Needs DATABASE_URL (a
database whose name contains "test"), AUTH_JWT_SECRET, AUTH_AES_HEX_KEY,
MASTER_ENCRYPTION_KEYSET and RESPONDENT_IDENTITY_KEY in the environment.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import jwt

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "backend" / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    command.upgrade(config, "head")

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from backend.jobs.schema import apply_schema

    async def jobs() -> None:
        engine = create_async_engine(
            os.environ["DATABASE_URL"], poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        async with engine.connect() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS jobs"))
        await engine.dispose()
        await apply_schema(os.environ["DATABASE_URL"])

    asyncio.run(jobs())
    print("migrated")


def _signing_members() -> list:
    ring = os.environ["AUTH_JWT_SECRET"]
    return ring.split(",") if "," in ring else [ring]


def _claims(user_id, email, *, typ="access", exp_in=4 * 3600, sid="x", extra=None):
    claims = {
        "id": user_id,
        "sub": email,
        "roles": ["FORM_CREATOR"],
        "plan": "FREE",
        "email_verified": True,
        "exp": int(time.time()) + exp_in,
        "jti": "j-" + user_id[-6:],
        "typ": typ,
    }
    if sid:
        claims["sid"] = sid
    claims.update(extra or {})
    return claims


def make_tokens(people, main_workspace_id):
    members = _signing_members()
    primary = members[0]
    old = members[1] if len(members) > 1 else None

    def mint(user_id, email, secret=None, **kw):
        return jwt.encode(_claims(user_id, email, **kw), secret or primary, algorithm="HS256")

    ws_id = main_workspace_id
    tokens = {}
    for name, p in people.items():
        tokens[name] = mint(p["id"], p["email"])
    tokens["owner_old_key"] = mint(people["owner"]["id"], people["owner"]["email"], secret=old) if old else None
    tokens["owner_unknown_key"] = mint(
        people["owner"]["id"], people["owner"]["email"], secret="z" * 40
    )
    tokens["owner_expired"] = mint(people["owner"]["id"], people["owner"]["email"], exp_in=-60)
    tokens["owner_refresh_typ"] = mint(people["owner"]["id"], people["owner"]["email"], typ="refresh")
    tokens["owner_no_typ"] = jwt.encode(
        {k: v for k, v in _claims(people["owner"]["id"], people["owner"]["email"]).items() if k != "typ"},
        primary, algorithm="HS256",
    )
    tokens["owner_no_sid"] = mint(people["owner"]["id"], people["owner"]["email"], sid=None)
    tokens["owner_hs512"] = jwt.encode(
        _claims(people["owner"]["id"], people["owner"]["email"]), primary, algorithm="HS512"
    )
    tokens["owner_respondent_scope"] = mint(
        people["owner"]["id"], people["owner"]["email"],
        extra={"session_scope": "respondent", "scope_workspace_id": ws_id},
    )
    tokens["owner_extra_claims"] = mint(
        people["owner"]["id"], people["owner"]["email"],
        extra={"auth_method": "otp", "mfa": True, "unknown_claim": [1, 2]},
    )
    tokens["owner_bad_id_claim"] = mint("not-an-objectid", "bad@example.test")
    tokens["owner_numeric_id"] = jwt.encode(
        {**_claims(people["owner"]["id"], people["owner"]["email"]), "id": 12345},
        primary, algorithm="HS256",
    )
    tokens["owner_nbf_future"] = mint(
        people["owner"]["id"], people["owner"]["email"],
        extra={"nbf": int(time.time()) + 3600},
    )
    owner = people["owner"]
    for name, extra in {
        "owner_bad_plan": {"plan": "GOLD"},
        "owner_pro_plan": {"plan": "PRO"},
        "owner_roles_string": {"roles": "ADMIN"},
        "owner_roles_null": {"roles": None},
        "owner_mfa_string": {"mfa": "yes"},
        "owner_mfa_bad": {"mfa": "maybe"},
        "owner_email_verified_one": {"email_verified": 1},
        "owner_email_verified_two": {"email_verified": 2},
        "owner_iat_future": {"iat": int(time.time()) + 3600},
        "owner_iat_past": {"iat": int(time.time()) - 3600},
        "owner_iat_text": {"iat": "now"},
        "owner_aud": {"aud": "someone"},
        "owner_iss": {"iss": "someone"},
        "owner_sid_number": {"sid": 5},
        "owner_sid_zero": {"sid": 0},
        "owner_scope_other_ws": {"session_scope": "respondent", "scope_workspace_id": "6a0000000000000000000000"},
        "owner_scope_none": {"session_scope": "respondent"},
        "owner_scope_bad_type": {"session_scope": 7},
        "owner_scope_unknown": {"session_scope": "weird"},
        "owner_auth_sso": {"auth_method": "sso", "sso_workspace_id": ws_id},
        "owner_float_exp": {"exp": time.time() + 3600.5},
        "owner_string_exp": {"exp": "9999999999"},
        "owner_nbf_past": {"nbf": int(time.time()) - 60},
    }.items():
        tokens[name] = mint(owner["id"], owner["email"], extra=extra)
    tokens["owner_extra_header"] = jwt.encode(
        _claims(owner["id"], owner["email"]), primary, algorithm="HS256", headers={"kid": "x", "typ": "JWT"}
    )
    tokens["garbage"] = "not.a.jwt"
    return tokens


async def seed(out: str) -> None:
    from common.ids import RecordId

    from backend.app.asgi import get_application, lifespan
    from backend.app.container import container
    from backend.app.models.enum.workspace_roles import WorkspaceRoles as R
    from backend.app.schemas.workspace_user import WorkspaceUserDocument
    from backend.app.services import workspace_service
    from common.models.user import User

    app = get_application(is_test_mode=True)
    members = _signing_members()
    primary = members[0]
    old = members[1] if len(members) > 1 else None

    def mint(user_id, email, secret=None, **kw):
        return jwt.encode(_claims(user_id, email, **kw), secret or primary, algorithm="HS256")

    people = {}

    def person(name):
        user_id = str(RecordId())
        people[name] = {"id": user_id, "email": f"{name}@example.test"}
        return User(id=user_id, sub=f"{name}@example.test")

    async with lifespan(app):
        workspace_repo = container.workspace_repo()
        member_repo = container.workspace_user_repo()

        owner = person("owner")
        await workspace_service.create_workspace(owner)
        ws = await workspace_repo.get_default_workspace_by_owner_id(owner.id)
        await workspace_repo.set_fields(ws, {"title": "Contract workspace"})

        roles = {
            "admin": [R.ADMIN],
            "editor": [R.EDITOR],
            "collaborator": [R.COLLABORATOR],
            "reviewer": [R.REVIEWER],
            "viewer": [R.VIEWER],
            "privacy": [R.PRIVACY_OFFICER],
            "coowner": [R.OWNER],
            "legacy_empty": [],
            "unknown_role": ["SUPERHERO"],
            "multi": [R.VIEWER, R.PRIVACY_OFFICER],
            "multi2": [R.REVIEWER, R.ADMIN],
            "privacy_editor": [R.PRIVACY_OFFICER, R.EDITOR],
        }
        for name, role_list in roles.items():
            u = person(name)
            await member_repo.save(
                WorkspaceUserDocument(workspace_id=ws.id, user_id=u.id, roles=role_list)
            )
        # a disabled member and a billing-owner whose membership row is disabled
        u = person("disabled_admin")
        await member_repo.save(
            WorkspaceUserDocument(
                workspace_id=ws.id, user_id=u.id, roles=[R.ADMIN], disabled=True
            )
        )
        person("stranger")  # signed in, member of nothing here
        person("nobody_workspace")  # owner of a workspace, not a member of ws

        other = person("other_owner")
        await workspace_service.create_workspace(other)
        other_ws = await workspace_repo.get_default_workspace_by_owner_id(other.id)

        # a disabled workspace (the billing owner was downgraded) with its owner,
        # an admin and an editor
        dis_owner = person("dis_owner")
        await workspace_service.create_workspace(dis_owner)
        dis_ws = await workspace_repo.get_default_workspace_by_owner_id(dis_owner.id)
        await workspace_repo.set_fields(dis_ws, {"disabled": True})
        for name, role_list in {
            "dis_admin": [R.ADMIN],
            "dis_editor": [R.EDITOR],
            "dis_coowner": [R.OWNER],
        }.items():
            u = person(name)
            await member_repo.save(
                WorkspaceUserDocument(workspace_id=dis_ws.id, user_id=u.id, roles=role_list)
            )

        # a workspace whose billing owner has no membership row at all
        ghost = person("ghost_owner")
        await workspace_service.create_workspace(ghost)
        ghost_ws = await workspace_repo.get_default_workspace_by_owner_id(ghost.id)
        await member_repo.delete(ghost_ws.id, ghost.id)

        # allowed origins for the CORS cases
        await container.allowed_origins_repo().add("https://app.example.test")

        tokens = make_tokens(people, str(ws.id))

        fixture = {
            "workspaces": {
                "main": str(ws.id),
                "other": str(other_ws.id),
                "disabled": str(dis_ws.id),
                "ghost": str(ghost_ws.id),
            },
            "people": people,
            "tokens": tokens,
        }
    Path(out).write_text(json.dumps(fixture, indent=1))
    print("seeded", len(people), "people")


async def extend(path: str) -> None:
    """Workspaces that require an authenticator app / single sign-on, for the runs
    that switch TOTP_ENABLED / SSO_ENABLED on."""
    from common.ids import RecordId

    from backend.app.asgi import get_application, lifespan
    from backend.app.container import container
    from backend.app.models.enum.workspace_roles import WorkspaceRoles as R
    from backend.app.schemas.workspace_user import WorkspaceUserDocument
    from backend.app.services import workspace_service
    from common.models.user import User

    fixture = json.loads(Path(path).read_text())
    app = get_application(is_test_mode=True)
    async with lifespan(app):
        repo, members = container.workspace_repo(), container.workspace_user_repo()
        for label, field in (("totp", "require_totp"), ("sso", "sso_required"), ("both", None)):
            owner_id = str(RecordId())
            owner = User(id=owner_id, sub=f"{label}_owner@example.test")
            await workspace_service.create_workspace(owner)
            ws = await repo.get_default_workspace_by_owner_id(owner.id)
            fields = {"require_totp": True, "sso_required": True} if field is None else {field: True}
            await repo.set_fields(ws, fields)
            fixture["people"][f"{label}_owner"] = {"id": owner_id, "email": owner.sub}
            admin_id = str(RecordId())
            await members.save(WorkspaceUserDocument(workspace_id=ws.id, user_id=admin_id, roles=[R.ADMIN]))
            fixture["people"][f"{label}_admin"] = {"id": admin_id, "email": f"{label}_admin@example.test"}
            fixture["workspaces"][label] = str(ws.id)
        # a disabled workspace that requires both: its owners keep read access
        owner_id = str(RecordId())
        owner = User(id=owner_id, sub="dis_both_owner@example.test")
        await workspace_service.create_workspace(owner)
        ws = await repo.get_default_workspace_by_owner_id(owner.id)
        await repo.set_fields(ws, {"require_totp": True, "sso_required": True, "disabled": True})
        fixture["people"]["dis_both_owner"] = {"id": owner_id, "email": owner.sub}
        fixture["workspaces"]["dis_both"] = str(ws.id)
    fixture["tokens"] = make_tokens(fixture["people"], fixture["workspaces"]["main"])
    for name in list(fixture["people"]):
        if name.endswith(("_owner", "_admin")) and name.split("_")[0] in ("totp", "sso", "both", "dis"):
            p = fixture["people"][name]
            fixture["tokens"][name + "_mfa"] = jwt.encode(
                _claims(p["id"], p["email"], extra={"mfa": True}), _signing_members()[0], algorithm="HS256")
            fixture["tokens"][name + "_apikey"] = jwt.encode(
                _claims(p["id"], p["email"], extra={"auth_method": "api_key"}), _signing_members()[0], algorithm="HS256")
            fixture["tokens"][name + "_sso"] = jwt.encode(
                _claims(p["id"], p["email"], extra={"auth_method": "sso", "sso_workspace_id": fixture["workspaces"].get(name.split("_")[0], "")}),
                _signing_members()[0], algorithm="HS256")
    Path(path).write_text(json.dumps(fixture, indent=1))
    print("extended")


def retoken(path: str) -> None:
    """New tokens for the people already seeded (the old ones expire after four hours)."""
    fixture = json.loads(Path(path).read_text())
    fixture["tokens"] = make_tokens(fixture["people"], fixture["workspaces"]["main"])
    Path(path).write_text(json.dumps(fixture, indent=1))
    print("tokens renewed")


if __name__ == "__main__":
    if sys.argv[1] == "migrate":
        migrate()
    elif sys.argv[1] == "extend":
        asyncio.run(extend(sys.argv[2]))
    elif sys.argv[1] == "retoken":
        retoken(sys.argv[2])
    else:
        asyncio.run(seed(sys.argv[2]))
