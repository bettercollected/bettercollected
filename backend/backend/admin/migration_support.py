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


def role_name(logical: str = "runtime") -> str:
    """The database role behind a logical name.

    ``runtime`` is ``bc_admin`` (``ADMIN_DB_RUNTIME_ROLE`` overrides it); any
    other logical name ``x`` is ``bc_x`` (``ADMIN_DB_ROLE_X`` overrides it), e.g.
    ``tasks`` -> ``bc_tasks``. Overrides exist for tests, whose roles carry a
    random suffix."""
    if logical == "runtime":
        name = os.environ.get("ADMIN_DB_RUNTIME_ROLE", "bc_admin")
    else:
        if not re.match(r"^[a-z][a-z0-9_]{0,40}$", logical):
            raise ValueError("logical role name must be lowercase letters, digits, _")
        name = os.environ.get(f"ADMIN_DB_ROLE_{logical.upper()}", f"bc_{logical}")
    if not _ROLE.match(name):
        raise ValueError("role override is not a plain role name")
    return name


def runtime_role() -> str:
    return role_name("runtime")


def grant(op, statement_template: str, role: str = "runtime") -> None:
    """Run ``statement_template`` (``{role}`` is the quoted role) for the logical
    ``role`` when that role exists; skip with a NOTICE otherwise (a scratch
    database without the roles script). deploy.sh creates the roles before
    migrating. Call it once per role that needs the privilege."""
    name = role_name(role)
    statement = statement_template.format(role=f'"{name}"').replace("'", "''")
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{name}') "
        f"THEN EXECUTE '{statement}'; "
        f"ELSE RAISE NOTICE 'role {name} does not exist; grant skipped'; END IF; END $$"
    )


def grant_roles(op, statement_template: str, roles: tuple[str, ...]) -> None:
    for role in roles:
        grant(op, statement_template, role)
