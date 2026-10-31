"""Every SECURITY DEFINER function runs with its owner's rights, so a role that can
call it, or fire the trigger it backs, must not be able to make it run something of
its own. The way in is the session's temporary schema: ``pg_temp`` is searched FIRST
for relations and types unless the function's ``search_path`` names it, and any login
role with TEMPORARY rights can create a temp table or type there. Hence one rule:
the ``search_path`` of every SECURITY DEFINER function ends in ``pg_temp``.

Two checks. One lists every such function in the migrated test database (admin
schemas, the roles script's definer functions); the other reads every SQL source in
the repository (migrations of every service, shell scripts, helpers), so a function
created in a service this database does not hold is checked too, and so is a future
one.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import text

from tests.admin.conftest import needs_postgres

ROOT = Path(__file__).resolve().parents[3]
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "tests", "dist", ".next"}
SUFFIXES = {".py", ".sh", ".sql"}


def _ends_in_pg_temp(config) -> bool:
    for entry in config or []:
        name, _, value = entry.partition("=")
        if name == "search_path":
            parts = [p.strip().strip('"') for p in value.split(",")]
            return bool(parts) and parts[-1] == "pg_temp"
    return False


@needs_postgres
async def test_every_security_definer_function_in_the_database_ends_in_pg_temp(
    owner_engine,
):
    async with owner_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT n.nspname, p.proname, p.proconfig FROM pg_proc p"
                    " JOIN pg_namespace n ON n.oid = p.pronamespace"
                    " WHERE p.prosecdef AND n.nspname NOT IN"
                    " ('pg_catalog', 'information_schema') ORDER BY 1, 2"
                )
            )
        ).all()
    assert rows, "no SECURITY DEFINER function found: the test proves nothing"
    exposed = [f"{s}.{n}" for s, n, config in rows if not _ends_in_pg_temp(config)]
    assert not exposed, f"search_path does not end in pg_temp: {exposed}"


@needs_postgres
async def test_the_executors_role_has_no_temporary_rights_after_the_roles_script(
    owner_engine, server
):
    # a database made from a template gets the default privileges again, so ask
    # the one the scripts ran in
    """The executor runs code that form creators wrote and needs no temp tables;
    the roles script takes TEMPORARY from PUBLIC and gives it back by name to the
    service roles that use it, not to this one."""
    async with owner_engine.connect() as conn:
        rows = {
            role: (
                await conn.execute(
                    text("SELECT has_database_privilege(:r, :d, 'TEMPORARY')"),
                    {"r": f"bc_{role}_{server.suffix}", "d": server.boot},
                )
            ).scalar()
            for role in ("jobs_exec", "app", "auth", "google")
        }
    assert rows == {"jobs_exec": False, "app": True, "auth": True, "google": True}


def _sources():
    for path in ROOT.rglob("*"):
        if path.suffix in SUFFIXES and path.is_file():
            relative = path.relative_to(ROOT)
            if any(part in SKIP_DIRS for part in relative.parts):
                continue
            yield path


# the part of a statement that names the function: from CREATE/ALTER FUNCTION up to
# the body's opening ($...$ or AS) or the end of the statement
_HEADER = re.compile(
    r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION|ALTER\s+FUNCTION)(?P<h>.*?)(?:\$|\bAS\b\s|;|'\s*\)|$)",
    re.IGNORECASE | re.DOTALL,
)


def _definer_headers(source: str):
    for match in _HEADER.finditer(source):
        header = match.group("h")
        if re.search(r"SECURITY\s+DEFINER", header, re.IGNORECASE):
            yield " ".join(header.split())


#: (file, function) of definitions that were replaced by a later migration which puts
#: pg_temp last. The database test above checks what is left after all migrations.
#: 0009's two functions were replaced by 0015 (the first dropped with its old
#: signature, the second re-created); in between they were callable only by the task
#: runner's role (EXECUTE and a ``session_user`` check), which has no TEMPORARY right.
SUPERSEDED = {
    ("0009_task_keyset_write.py", "settings.task_notify_reencrypt"),
    ("0009_task_keyset_write.py", "settings.task_write_keyset"),
}


def _search_path(header: str, source: str):
    found = re.search(
        r"search_path\s*=\s*((?:[\w\"]+\s*,\s*)*[\w\"]+|\{\w+\})", header, re.IGNORECASE
    )
    if not found:
        return None
    value = found.group(1)
    if value.startswith("{"):  # a constant of the same file, as backend/jobs/schema.py has
        constant = re.search(rf'{value[1:-1]}\s*=\s*"([^"]*)"', source)
        if not constant:
            return None
        value = constant.group(1)
    return [part.strip().strip('"') for part in value.split(",")]


def test_every_security_definer_in_the_repository_ends_in_pg_temp():
    seen, exposed = 0, []
    for path in _sources():
        source = path.read_text(errors="ignore")
        if "SECURITY DEFINER" not in source.upper():
            continue
        for header in _definer_headers(source):
            name = re.match(r"\s*(?:FUNCTION\s+)?([\w.]+)", header)
            if (path.name, name.group(1) if name else "") in SUPERSEDED:
                continue
            seen += 1
            parts = _search_path(header, source)
            if not parts or parts[-1] != "pg_temp":
                exposed.append(f"{path.relative_to(ROOT)}: {header[:110]}")
    assert seen >= 20, f"only {seen} SECURITY DEFINER statements found: the scan is broken"
    assert not exposed, "\n".join(exposed)
