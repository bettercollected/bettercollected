"""Which processes read the four 4.4 switches, checked against the settings inventory.

The inventory (``common/settings/inventory.py``) lists, for every setting, the services
that read it; the settings page and an operator who sets the environment service by
service rely on it. The four switches below are read by code in many modules, and a
reader that the inventory does not name is a service that silently keeps the default
(`FORM_ACCESS_ENABLED` was found read by the jobs worker while the inventory said
"backend" only).

This test reads the source of the backend package and finds, for each switch, every
module that reads it: one that imports the switch's ``mode`` module, or that reads
``settings.<group>``. The modules are listed below with the process that reaches them:

* ``http``: only requests to the backend (routes, the MCP server, the public API);
* ``jobs``: also code the jobs worker runs (its tasks call these through a service).

A module that is not in the table fails the test: decide which process reaches it, add
it here, and make the inventory's reader list agree. The inventory is then compared to
the table (the jobs worker is a reader exactly when a module is marked ``jobs``).

Covered: these four switches, whole backend package. Not covered: other settings, and
the paths into a module (a module marked ``http`` is reviewed, not proven unreachable
from a job).
"""

import ast
from pathlib import Path

import pytest

from common.settings.inventory import BACKEND, JOBS, all_specs

BACKEND_PACKAGE = Path(__file__).resolve().parents[3] / "backend" / "backend"

# switch -> (modules that are the switch's own accessor, the ``settings.<group>`` it reads)
SWITCHES = {
    "FORM_ACCESS_ENABLED": (("backend.app.services.form_access.mode",), "form_access"),
    "API_KEY_ROLES_ENABLED": (("backend.app.services.api_key_roles.mode",), "api_key_roles"),
    "AUDIT_LOG_UI_ENABLED": (("backend.app.services.audit_log.mode",), "AUDIT_LOG_UI_ENABLED"),
    "FORM_PROMOTION_ENABLED": (("backend.app.services.form_promotion.mode",), "form_promotion"),
}

_WORKSPACE_ROUTER = "backend/app/controllers/workspace_router.py"

READERS = {
    "FORM_ACCESS_ENABLED": {
        _WORKSPACE_ROUTER: "http",
        "backend/app/repositories/postgres/forms.py": "http",
        "backend/app/services/ai/chat.py": "http",
        "backend/app/services/ai/insights.py": "http",
        "backend/app/services/ai/proposals.py": "http",
        "backend/app/services/ai/review.py": "http",
        "backend/app/services/analytics_service.py": "http",
        "backend/app/services/api_access.py": "http",
        # every decision on a form: the jobs worker reaches it from the email actions'
        # team recipients (member_ids_holding) and from a response export's permission
        # check (has_permission with the form)
        "backend/app/services/authorization_service.py": "jobs",
        "backend/app/services/form_access/admin.py": "http",
        "backend/app/services/form_access/service.py": "jobs",  # the decision authorization_service makes
        "backend/app/services/form_access/startup.py": "http",  # the backend's own startup
        "backend/app/services/form_response_service.py": "http",
        "backend/app/services/form_service.py": "http",
        "backend/app/services/form_spec/editor_ops.py": "http",
        "backend/app/services/form_spec/service.py": "http",
        "backend/app/services/integration_service.py": "http",
        "backend/app/services/open_formulieren_export_service.py": "http",
        "backend/app/services/option_sources/service.py": "http",
        "backend/app/services/respondent_feedback_service.py": "http",
        "backend/app/services/response_export/service.py": "http",
        "backend/app/services/scim/directory_service.py": "http",
        "backend/app/services/workspace_form_service.py": "http",
    },
    "API_KEY_ROLES_ENABLED": {
        _WORKSPACE_ROUTER: "http",
        "backend/app/services/ai/api_keys.py": "http",
    },
    "AUDIT_LOG_UI_ENABLED": {
        _WORKSPACE_ROUTER: "http",
        "backend/app/services/audit_log/export.py": "http",
        "backend/app/services/audit_log/reader.py": "http",
        # the daily purge (audit_log_purge, run by the jobs worker) is in this module too
        # and never reads the switch: refuse_when_off is called by the routes only
        "backend/app/services/audit_log/retention.py": "http",
    },
    "FORM_PROMOTION_ENABLED": {
        _WORKSPACE_ROUTER: "http",
        "backend/app/controllers/form_promotion_router.py": "http",
    },
}


def _relative(path: Path) -> str:
    return "backend/" + path.relative_to(BACKEND_PACKAGE).as_posix()


def _module(path: Path) -> str:
    return "backend." + path.relative_to(BACKEND_PACKAGE).with_suffix("").as_posix().replace("/", ".")


def _reads(tree: ast.AST, accessors, group: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module in accessors:
                return True
            if any(a == f"{node.module}.{alias.name}" for a in accessors for alias in node.names):
                return True
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == group
            and isinstance(node.value, ast.Name)
            and node.value.id == "settings"
        ):
            return True
    return False


def _found(switch: str) -> set:
    accessors, group = SWITCHES[switch]
    found = set()
    for path in sorted(BACKEND_PACKAGE.rglob("*.py")):
        relative = _relative(path)
        if "/migrations/" in relative or "/config/" in relative or _module(path) in accessors:
            continue
        if _reads(ast.parse(path.read_text()), accessors, group):
            found.add(relative)
    return found


@pytest.mark.parametrize("switch", sorted(SWITCHES))
def test_every_reader_module_is_known(switch):
    found = _found(switch)
    known = set(READERS[switch])
    assert found == known, (
        f"{switch}: modules that read it changed. New: {sorted(found - known)}; "
        f"gone: {sorted(known - found)}. For a new one decide whether the jobs worker "
        "reaches it, add it to READERS in this test, and keep the reader list of the "
        "setting in common/settings/inventory.py (and docs/settings-inventory.md) in step."
    )


@pytest.mark.parametrize("switch", sorted(SWITCHES))
def test_the_inventory_names_the_processes_that_read_it(switch):
    (spec,) = [s for s in all_specs() if s.key == switch]
    expected = {BACKEND} | ({JOBS} if "jobs" in READERS[switch].values() else set())
    assert set(spec.readers) == expected, (
        f"{switch}: the inventory lists {sorted(spec.readers)}, the code is read by {sorted(expected)}"
    )
