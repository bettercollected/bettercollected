"""Database rules of the setup wizard's tables (migration 0012), as the runtime role."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.admin.conftest import needs_postgres

pytestmark = needs_postgres


async def test_setup_state_rules_for_the_runtime_role(runtime_engine):
    async with runtime_engine.begin() as conn:
        await conn.execute(text("INSERT INTO admin.setup_state (started_by) VALUES ('a@example.org')"))
    for sql in (
        "INSERT INTO admin.setup_state (started_by) VALUES ('b@example.org')",  # one row only
        "DELETE FROM admin.setup_state",  # never removed
        "UPDATE admin.setup_state SET started_by = 'x'",  # who started it is fixed
        "UPDATE admin.setup_state SET started_at = now()",
        "UPDATE admin.setup_state SET mail_step = 'bogus'",
    ):
        with pytest.raises(Exception):
            async with runtime_engine.begin() as conn:
                await conn.execute(text(sql))
    async with runtime_engine.begin() as conn:
        await conn.execute(text("UPDATE admin.setup_state SET mail_step = 'saved'"))
        await conn.execute(
            text("UPDATE admin.setup_state SET completed_at = now(), completed_by = 'a@example.org'")
        )


async def test_session_states_are_limited_to_the_three_known(runtime_engine):
    base = (
        "INSERT INTO admin.sessions (token_hash, email, mfa_state, idle_expires_at, abs_expires_at) "
        "VALUES (decode(:h, 'hex'), 'a@example.org', :s, now() + interval '1 hour', "
        "now() + interval '1 hour')"
    )
    for i, state in enumerate(("email_ok", "mfa_ok", "setup")):
        async with runtime_engine.begin() as conn:
            await conn.execute(text(base), {"h": f"{i:02x}" * 32, "s": state})
    with pytest.raises(Exception):
        async with runtime_engine.begin() as conn:
            await conn.execute(text(base), {"h": "ff" * 32, "s": "superuser"})
