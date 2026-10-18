"""Helpers for the admin revisions: privileges for the runtime role.

The migration role owns every table; the runtime role (``bc_admin`` by default,
``ADMIN_DB_RUNTIME_ROLE`` to override, as the tests do) gets exactly what each
table needs, granted explicitly per table. There are deliberately no default
privileges: a table added later gets nothing until its revision says so, and
``audit_log`` can never inherit UPDATE or DELETE.
"""

from __future__ import annotations

import os
import re

_ROLE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")


def runtime_role() -> str:
    role = os.environ.get("ADMIN_DB_RUNTIME_ROLE", "bc_admin")
    if not _ROLE.match(role):
        raise ValueError("ADMIN_DB_RUNTIME_ROLE is not a plain role name")
    return role


def grant(op, statement_template: str) -> None:
    """Run ``statement_template`` (``{role}`` is the quoted runtime role) when the
    role exists; skip with a NOTICE otherwise (a scratch database without the
    roles script). deploy.sh creates the roles before migrating."""
    role = runtime_role()
    statement = statement_template.format(role=f'"{role}"').replace("'", "''")
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
        f"THEN EXECUTE '{statement}'; "
        f"ELSE RAISE NOTICE 'role {role} does not exist; grant skipped'; END IF; END $$"
    )
