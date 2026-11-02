"""Every handler a workspace API key can reach goes through ``api_access``.

The public REST API (``public_api/``) and the MCP server (``mcp/``) are mounted
apps outside the root router. A route or tool added to either that skips the
key gate would hand a key more than its role and its list of forms allow, and the
runtime matrix (``tests/app/form_access/test_key_matrix.py``) only sees what it is
told about. This guard reads the source, in the manner of
``test_form_access_call_sites.py``:

* every public route takes the ``api_key(scope, ...)`` dependency, with the scope
  the matrix classifies it under, and a route that makes a form says
  ``creates=True``;
* every MCP tool starts with ``_key(scope, ...)``, with the scope the matrix
  classifies it under, and a tool that makes a form says ``creates=<its name>``;
* a call that reads a form or the workspace's forms from those two packages sits
  in a function that also goes through the key gate (``restrict_to_key_visible``,
  ``_workspace_form_ids``, ``key_may_use_form``, ``require_key_on_form``,
  ``_require_form``, ``require_key_scope``), or is named in ``ALLOWED`` with the
  reason; an entry that no longer matches fails too, so the list cannot rot;
* the acting user of a key is built in one place (``api_access.acting_user``);
* only ``api_access`` and the key service read a key's ``form_scope`` or role, or
  write its rows;
* the edit of a key's list of forms still checks every form with
  ``_checked_list`` and ``_checked_list`` still asks ``restrict_to_visible``.
"""

import ast
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Set, Tuple

from backend.app.services.submissions_api.mode import SCOPE as SUBMISSIONS_SCOPE
from tests.app.form_access.test_key_matrix import MCP, PUBLIC
from tests.app.services.test_form_access_call_sites import (
    PACKAGE,
    _callee,
    _calls_in,
    _functions,
    _is_decorated_with,
)

APP = PACKAGE / "app"
SURFACES = ("public_api", "mcp")
VERBS = {"get", "post", "put", "patch", "delete"}

GATES = {
    "restrict_to_key_visible",
    "_workspace_form_ids",
    "key_may_use_form",
    "require_key_on_form",
    "_require_form",
    "require_key_scope",
}
# calls that read a form, the workspace's forms or a form's data
DATA_CALLS = {
    "list_in_workspace",
    "find_workspace_form",
    "get_forms_by_form_ids",
    "get_form_ids_in_workspace",
    "get_form_document_by_id",
    "response_scope",
    "list_deletion_requests_for_form_ids",
}

# (file, function, call) -> why that read is not a way round the key's gate
ALLOWED: Dict[Tuple[str, str, str], str] = {
    ("app/public_api/routes.py", "_require_form", "find_workspace_form"): (
        "only checks that the form is one of the key's workspace; every route that "
        "calls it has already been decided on the form by the api_key dependency "
        "(require_key_scope with the path's form_id)"
    ),
}


class Call(NamedTuple):
    path: str
    function: str
    name: str
    line: int
    gated: bool


def _source(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def _surface_files() -> Iterator[Path]:
    for surface in SURFACES:
        yield from sorted((APP / surface).rglob("*.py"))


def data_calls(files: List[Path], root: Path) -> List[Call]:
    found: List[Call] = []

    def walk(node, scope: Tuple[str, ...], path: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = scope + (child.name,)
                calls = _calls_in(child)
                # a call belongs to the innermost function around it
                nested = [
                    n
                    for n in ast.iter_child_nodes(child)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                own = {
                    id(c)
                    for c in ast.walk(child)
                    if isinstance(c, ast.Call)
                    and not any(c in ast.walk(n) for n in nested)
                }
                for call in ast.walk(child):
                    if isinstance(call, ast.Call) and id(call) in own:
                        name = _callee(call)
                        if name in DATA_CALLS:
                            found.append(
                                Call(
                                    path,
                                    ".".join(inner),
                                    name,
                                    call.lineno,
                                    bool(GATES & calls),
                                )
                            )
                walk(child, inner, path)
            else:
                walk(child, scope, path)

    for file in files:
        walk(_source(file), (), file.relative_to(root).as_posix())
    return found


# =========================================================================== public routes
def _route_decorators(function) -> List[Tuple[str, str]]:
    """``(verb, path)`` for each ``@router.<verb>("path", ...)`` of a function."""
    found = []
    for decorator in function.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in VERBS
            and decorator.args
            and isinstance(decorator.args[0], ast.Constant)
        ):
            found.append((decorator.func.attr.upper(), decorator.args[0].value))
    return found


def _api_key_calls(function) -> List[ast.Call]:
    return [
        call
        for default in (*function.args.defaults, *function.args.kw_defaults)
        if default is not None
        for call in ast.walk(default)
        if isinstance(call, ast.Call) and _callee(call) == "api_key"
    ]


def _literal(call: ast.Call, position: int = 0) -> Optional[str]:
    if len(call.args) > position and isinstance(call.args[position], ast.Constant):
        return call.args[position].value
    return None


def _scope_of(call: ast.Call, constants: Dict[str, str]) -> Optional[str]:
    """The scope argument of ``api_key``/``_key``: a literal, or a module constant."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant):
        return first.value
    if isinstance(first, ast.Name):
        return constants.get(first.id)
    return None


def _string_constants(tree: ast.AST) -> Dict[str, str]:
    values = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            values[node.targets[0].id] = node.value.value
    return values


def _flag(call: ast.Call, name: str) -> bool:
    return any(
        k.arg == name and isinstance(k.value, ast.Constant) and bool(k.value.value)
        for k in call.keywords
    )


def public_handlers() -> Iterator[Tuple[ast.AST, str, str]]:
    for function in _functions(APP / "public_api" / "routes.py"):
        for verb, path in _route_decorators(function):
            yield function, verb, path


def test_the_public_api_registers_routes_in_one_place_only():
    """Every route lives in ``public_api/routes.py``'s one router; nothing else in
    the package registers a route, so the guard below sees them all."""
    for file in _surface_files():
        if file.parent.name != "public_api" or file.name == "routes.py":
            continue
        for node in ast.walk(_source(file)):
            registers = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"add_api_route", "add_route"}
            ) or (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _route_decorators(node)
            )
            assert not registers, (
                f"{file.relative_to(APP)}:{node.lineno} registers a route outside "
                "public_api/routes.py"
            )
    routers = [
        n
        for n in ast.walk(_source(APP / "public_api" / "routes.py"))
        if isinstance(n, ast.Call) and _callee(n) == "APIRouter"
    ]
    assert len(routers) == 1


def test_every_public_route_takes_the_key_dependency_with_its_scope():
    constants = _string_constants(_source(APP / "public_api" / "routes.py"))
    constants["SUBMISSIONS_SCOPE"] = SUBMISSIONS_SCOPE  # imported by the routes
    seen = 0
    for function, verb, path in public_handlers():
        seen += 1
        keys = _api_key_calls(function)
        assert len(keys) == 1, (
            f"{verb} {path} ({function.name}) must take exactly one "
            "Depends(api_key(scope, operation)): that dependency is what decides the "
            "key, its role and its list of forms before the handler runs"
        )
        entry = PUBLIC.get((verb, path))
        assert entry is not None, f"{verb} {path} is not classified in test_key_matrix.PUBLIC"
        scope = _scope_of(keys[0], constants)
        assert scope == entry.scope, (
            f"{verb} {path}: api_key asks for scope {scope!r} but the matrix "
            f"classifies it under {entry.scope!r}"
        )
        assert _flag(keys[0], "creates") == (entry.kind == "create"), (
            f"{verb} {path}: creates=True must be set on exactly the routes that make "
            "a form (a key limited to a list of forms makes none)"
        )
    assert seen == len([k for k, e in PUBLIC.items() if e.kind != "document"]), seen


def test_a_route_that_decides_on_a_form_does_it_before_it_reads_anything():
    """A route on a form either leaves it to the dependency (the path's ``form_id``)
    or, for the submissions routes (which judge the key's own submission list
    first), calls ``require_key_on_form`` itself, before the budget of the form."""
    for function, verb, path in public_handlers():
        entry = PUBLIC[(verb, path)]
        if entry.kind not in ("form_bound", "response_bound"):
            continue
        (key,) = _api_key_calls(function)
        if _flag(key, "submissions"):
            assert "require_key_on_form" in _calls_in(function), (
                f"{verb} {path}: a submissions route must call require_key_on_form"
            )
            calls = [
                _callee(n)
                for n in ast.walk(function)
                if isinstance(n, ast.Call) and _callee(n)
            ]
            order = [c for c in calls if c in ("require_key_on_form", "form_budget")]
            assert order[:2] == ["require_key_on_form", "form_budget"], (
                f"{verb} {path}: the form is decided before its budget is spent"
            )


# =========================================================================== MCP tools
def mcp_tools() -> List[ast.AsyncFunctionDef]:
    return [
        f
        for f in _functions(APP / "mcp" / "server.py")
        if _is_decorated_with(f, "mcp", "tool")
    ]


def _first_statement(function) -> ast.stmt:
    for statement in function.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            continue
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and isinstance(statement.value.value, str)
        ):
            continue  # the docstring
        return statement
    raise AssertionError(function.name)


def _awaited_key_call(statement: ast.stmt) -> Optional[ast.Call]:
    value = getattr(statement, "value", None)
    if isinstance(value, ast.Await) and isinstance(value.value, ast.Call):
        if _callee(value.value) == "_key":
            return value.value
    return None


def test_every_mcp_tool_starts_with_the_key_gate_for_its_scope():
    tools = mcp_tools()
    assert len(tools) == len(MCP), [t.name for t in tools]
    for tool in tools:
        entry = MCP.get(tool.name)
        assert entry is not None, f"MCP tool {tool.name} is not classified in test_key_matrix.MCP"
        call = _awaited_key_call(_first_statement(tool))
        assert call is not None, (
            f"MCP tool {tool.name} must start with `key = await _key(scope)`: it "
            "authenticates the key, counts its budget and checks its role"
        )
        assert _scope_of(call, {}) == entry.scope, (
            f"{tool.name}: _key asks for scope {_scope_of(call, {})!r} but the matrix "
            f"classifies it under {entry.scope!r}"
        )
        creates = [k for k in call.keywords if k.arg == "creates"]
        if entry.kind == "create":
            assert creates and isinstance(creates[0].value, ast.Constant) and (
                creates[0].value.value == tool.name
            ), f"{tool.name} makes a form: `_key(..., creates={tool.name!r})`"
        else:
            assert not creates, f"{tool.name} is not a creating tool"


def test_every_mcp_tool_on_a_form_or_a_response_decides_on_it():
    for tool in mcp_tools():
        entry = MCP[tool.name]
        calls = _calls_in(tool)
        if entry.kind == "form_bound":
            assert "_require_form" in calls, f"{tool.name} names a form: _require_form"
        if entry.kind == "response_bound":
            assert "key_may_use_form" in calls, (
                f"{tool.name} names a response: decide on its form with key_may_use_form "
                "before anything is decrypted"
            )
        if entry.kind in ("list", "privacy_queue"):
            assert "_workspace_form_ids" in calls, (
                f"{tool.name} lists forms or what hangs on them: narrow with "
                "_workspace_form_ids (restrict_to_key_visible)"
            )


# =========================================================================== reads of forms
def test_a_read_of_forms_in_a_surface_goes_through_the_key_gate():
    calls = data_calls(list(_surface_files()), PACKAGE)
    assert len(calls) >= 6, calls  # the scan sees the reads
    bad = [
        c
        for c in calls
        if not c.gated and (c.path, c.function, c.name) not in ALLOWED
    ]
    assert not bad, (
        "a function of public_api/ or mcp/ reads forms without going through the key "
        "gate (restrict_to_key_visible, _workspace_form_ids, key_may_use_form, "
        "require_key_on_form, _require_form, require_key_scope). Gate it, or add it to "
        "ALLOWED in tests/app/services/test_key_call_sites.py with the reason:\n"
        + "\n".join(f"  {c.path}:{c.line} {c.function} -> {c.name}" for c in bad)
    )


def test_every_allowed_read_still_matches_a_call():
    live = {
        (c.path, c.function, c.name) for c in data_calls(list(_surface_files()), PACKAGE)
    }
    stale = sorted(set(ALLOWED) - live)
    assert not stale, f"ALLOWED entries that match no call any more (remove them): {stale}"
    for key, reason in ALLOWED.items():
        assert len(reason.strip()) >= 30, f"{key}: say why"


def test_the_read_guard_catches_an_ungated_read(tmp_path):
    source = tmp_path / "app" / "mcp" / "bad.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "async def leaks(key):\n"
        "    return await repo.list_in_workspace(key.workspace_id)\n"
        "async def gated(key):\n"
        "    ids = await repo.list_in_workspace(key.workspace_id)\n"
        "    return await restrict_to_key_visible(key, ids, [])\n"
        "async def outer(key):\n"
        "    await _require_form(key, 's', 'f')\n"
        "    async def inner():\n"
        "        return await repo.find_workspace_form(1, 2)\n"
        "    return await inner()\n"
    )
    found = {(c.function, c.name): c.gated for c in data_calls([source], tmp_path)}
    assert found == {
        ("leaks", "list_in_workspace"): False,
        ("gated", "list_in_workspace"): True,
        ("outer.inner", "find_workspace_form"): False,
    }


# =========================================================================== the key's own state
# the places that may read a key's role or form scope, or build its rows
KEY_STATE_FILES = {
    "app/services/api_access.py",
    "app/services/ai/api_keys.py",
    "app/services/api_key_roles/model.py",
    "app/services/api_key_roles/validation.py",
    "app/services/api_key_roles/mode.py",
    "app/repositories/postgres/form_access.py",
    "app/repositories/postgres/identity.py",
    "app/services/audit_log/reader.py",  # an audit row's own form_scope field
}
KEY_STATE_ATTRIBUTES = {"form_scope", "key_ceiling"}


def key_state_uses(root: Path) -> List[Tuple[str, int, str]]:
    found = []
    for file in sorted(root.rglob("*.py")):
        relative = file.relative_to(root.parent).as_posix()
        if relative.startswith("app/schemas/"):
            continue  # the documents' own fields
        for node in ast.walk(_source(file)):
            if isinstance(node, ast.Attribute) and node.attr in KEY_STATE_ATTRIBUTES:
                found.append((relative, node.lineno, node.attr))
            elif isinstance(node, ast.Name) and node.id == "SUBJECT_KEY":
                found.append((relative, node.lineno, "SUBJECT_KEY"))
            elif (
                isinstance(node, ast.Attribute)
                and node.attr == "role"
                and isinstance(node.value, (ast.Name, ast.Attribute))
                and (
                    getattr(node.value, "id", None) in {"key", "document", "stored"}
                    or getattr(node.value, "attr", None) == "key"
                )
                and "api_key" in file.read_text()
            ):
                found.append((relative, node.lineno, "role"))
    return found


def test_only_the_key_gate_and_the_key_service_read_a_keys_limits():
    uses = key_state_uses(APP)
    assert len(uses) >= 10, uses  # the scan sees them
    outside = sorted({u for u in uses if u[0] not in KEY_STATE_FILES})
    assert not outside, (
        "a key's role, form scope or rows are read or built outside api_access / the key "
        "service: decide through api_access instead (key_permissions_on_form, "
        "require_key_on_form, restrict_to_key_visible), or add the file to "
        "KEY_STATE_FILES with a reason:\n"
        + "\n".join(f"  {p}:{n} {what}" for p, n, what in outside)
    )


def test_the_acting_user_of_a_key_is_built_in_one_place():
    """``User(..., auth_method="api_key", ...)`` appears in ``api_access.acting_user``
    only, and ``acting_user`` itself is called from the three places that need it."""
    builders = []
    callers: Set[str] = set()
    for file in sorted(APP.rglob("*.py")):
        relative = file.relative_to(PACKAGE).as_posix()
        for node in ast.walk(_source(file)):
            if isinstance(node, ast.Call):
                if any(
                    k.arg == "auth_method"
                    and isinstance(k.value, ast.Constant)
                    and k.value.value == "api_key"
                    for k in node.keywords
                ):
                    builders.append(relative)
                if _callee(node) == "acting_user":
                    callers.add(relative)
    assert builders == ["app/services/api_access.py"], builders
    assert callers == {
        "app/services/api_access.py",
        "app/services/ai/api_keys.py",
        "app/mcp/server.py",
        "app/public_api/auth.py",
    }, callers


# =========================================================================== the edit's list
def _function(path: Path, qualified: str) -> ast.AST:
    parts = qualified.split(".")
    nodes = list(ast.walk(_source(path)))
    for node in nodes:
        if isinstance(node, ast.ClassDef) and node.name == parts[0]:
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    member.name == parts[1]
                ):
                    return member
    raise AssertionError(qualified)


def test_the_list_of_a_key_is_checked_with_what_the_editor_may_open():
    """The edit (``update_key`` -> ``_plan_edit``) and the creation both check every
    form of a key's list with ``_checked_list``, which asks ``restrict_to_visible``
    for the person editing: a form they cannot open cannot be put on a key's list.
    (``test_key_routes.py`` runs it.)"""
    keys = APP / "services" / "ai" / "api_keys.py"
    assert "_checked_list" in _calls_in(_function(keys, "APIKeyService._plan_edit"))
    assert "_checked_list" in _calls_in(_function(keys, "APIKeyService.create_key"))
    assert "_plan_edit" in _calls_in(_function(keys, "APIKeyService.update_key"))
    assert "restrict_to_visible" in _calls_in(_function(keys, "APIKeyService._checked_list"))
    # and nothing else sets a key's role or form scope: the one writer is the
    # repository's update_limits, called by update_key only
    callers = [
        file.relative_to(PACKAGE).as_posix()
        for file in APP.rglob("*.py")
        if "update_limits" in file.read_text() and "def update_limits" not in file.read_text()
    ]
    assert callers == ["app/services/ai/api_keys.py"], callers
