"""Form-level access: a decision made in a function that is about one form has
to be made ON that form.

``AuthorizationService.authorize`` / ``has_permission`` / ``effective_permissions``
decide on the workspace's roles alone unless they are given ``form_id``; with it
(and ``FORM_ACCESS_ENABLED`` on) they apply the form's grants and its access
mode. A call that forgets it in a function that holds a form id is a restricted
form its members can open. The same goes for the key checks of the public API
and the MCP server (``require_key_scope`` / ``require_key_on_form``).

The guard walks the backend's source. Every such call in a function that
receives a form id (a parameter named ``form_id`` or ``..._form_id``, or the slug,
response id or submission id a form is resolved from; the function or any
function around it) must pass it. Anything else needs an entry
in ``ALLOWED`` with the reason, and an entry that no longer matches a call fails
too, so the list cannot rot. A new call without a form id, or a new function
with a form id that asks the workspace only, fails here, naming file and line.

The route-level counterpart (every route that carries a form id is classified
and run per role, mode and grant) is
``tests/app/form_access/test_route_matrix.py``.
"""

import ast
import re
from pathlib import Path
from typing import Dict, Iterator, List, NamedTuple, Optional, Set, Tuple


import backend

PACKAGE = Path(backend.__file__).parent  # backend/backend
SCANNED = ("app",)  # services, controllers, public API, MCP, ...

# call name -> the position of ``form_id`` among the positional arguments
DECISIONS: Dict[str, int] = {
    "authorize": 3,  # (user, permission, workspace_id, form_id, ...)
    "has_permission": 3,  # (user, permission, workspace_id, form_id)
    "effective_permissions": 3,  # (user, workspace_id, raise_sso_required, form_id)
    "require_key_scope": 2,  # (key, scope, form_id=None)
    "require_key_on_form": 2,  # (key, scope, form_id)
}
FORM_PARAMETER = re.compile(
    r"(^|_)(form_ids?|slug|response_id|submission_id)$"
)
# a form id that arrives inside a request body or a query object rather than as
# an argument of its own: ``request.form_id``, ``body.source.form_id``, ``dto.form_ids``
BODY_FORM_ATTRIBUTES = {"form_id", "form_ids", "formId", "formIds", "submission_form_ids"}


def _reads_a_form_from_a_parameter(function) -> bool:
    parameters = {p for p in _parameters(function) if p not in ("self", "cls")}
    for node in ast.walk(function):
        if isinstance(node, ast.Attribute) and node.attr in BODY_FORM_ATTRIBUTES:
            base = node.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name) and base.id in parameters:
                return True
    return False


class Site(NamedTuple):
    path: str  # relative to backend/backend
    function: str  # dotted qualified name
    call: str
    line: int
    passes_form: bool
    in_form_function: bool


def _passes_form(call: ast.Call, name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg == "form_id":
            value = keyword.value
            return not (isinstance(value, ast.Constant) and value.value is None)
        if keyword.arg is None:  # **options: cannot be told, so it is not trusted
            return False
    position = DECISIONS[name]
    if len(call.args) > position:
        value = call.args[position]
        return not (isinstance(value, ast.Constant) and value.value is None)
    return False


def _callee(call: ast.Call) -> Optional[str]:
    function = call.func
    if isinstance(function, ast.Attribute):
        return function.attr
    if isinstance(function, ast.Name):
        return function.id
    return None


def _parameters(node) -> List[str]:
    args = node.args
    names = [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


def sites_in(path: Path, root: Path) -> Iterator[Site]:
    tree = ast.parse(path.read_text(), filename=str(path))
    relative = path.relative_to(root).as_posix()

    def walk(node, scope: Tuple[str, ...], form_function: bool) -> Iterator[Site]:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inner = scope + (child.name,)
                has_form = (
                    form_function
                    or any(FORM_PARAMETER.search(p) for p in _parameters(child))
                    or _reads_a_form_from_a_parameter(child)
                )
                yield from walk(child, inner, has_form)
                continue
            if isinstance(child, ast.ClassDef):
                yield from walk(child, scope + (child.name,), form_function)
                continue
            if isinstance(child, ast.Call):
                name = _callee(child)
                if name in DECISIONS:
                    yield Site(
                        relative,
                        ".".join(scope) or "<module>",
                        name,
                        child.lineno,
                        _passes_form(child, name),
                        form_function,
                    )
            yield from walk(child, scope, form_function)

    yield from walk(tree, (), False)


def all_sites(root: Path = PACKAGE) -> List[Site]:
    found: List[Site] = []
    for part in SCANNED:
        for path in sorted((root / part).rglob("*.py")):
            found.extend(sites_in(path, root))
    return found


# (file, function, call) -> why this call decides on the workspace alone in a
# function that holds a form id. Every reason says what decides on the form
# instead, or why no form-level decision can differ (the permission is never
# granted per form and Owner/Admin always hold it).
ALLOWED: Dict[Tuple[str, str, str], str] = {
    (
        "app/controllers/option_lists_router.py",
        "OptionListsRouter.preview_option_source",
        "authorize",
    ): (
        "form.edit at workspace level; body.form_id is only the form being edited, "
        "compared with the source's form to refuse a form that takes its options "
        "from its own answers (nothing of it is read or returned); the source's "
        "form is decided in authorize_source (a form closed to the caller does "
        "not exist for them)"
    ),
    (
        "app/services/form_promotion/service.py",
        "FormPromotionService._target_permission",
        "effective_permissions",
    ): (
        "whether the caller is a member of the TARGET workspace at all (nothing held: "
        "the 404 of a workspace that does not exist); the form here is the "
        "source's, decided in _source_link, and the target form (when there is one) "
        "is decided by the authorize below with its own form id"
    ),
    (
        "app/services/form_promotion/service.py",
        "FormPromotionService._target_permission",
        "authorize",
    ): (
        "form.create in the target workspace (no target form exists yet: workspace "
        "level, the source's form id belongs to the other workspace); an existing "
        "target form is decided in the same function with its own form id"
    ),
    (
        "app/services/form_promotion/service.py",
        "FormPromotionService.targets",
        "effective_permissions",
    ): (
        "membership of the target workspace (nothing held: 404); the forms listed "
        "are narrowed to those the caller may edit by visible_form_ids, which is "
        "decided per form, and the source form is decided in _source_link"
    ),
    ("app/services/ai/api_keys.py", "APIKeyService.create_key", "authorize"): (
        "security.manage is Owner/Admin-only and never granted per form; "
        "submission_form_ids are checked to be forms of this workspace "
        "(_checked_submission_forms), and an Owner or Admin reaches every form"
    ),
    (
        "app/services/response_import/service.py",
        "ResponseImportService._process",
        "has_permission",
    ): (
        "the background re-check that the person who started the import still "
        "holds response.import, which is Owner/Admin-only and never granted per "
        "form; the form is the import's own"
    ),
    (
        "app/services/workspace_form_service.py",
        "WorkspaceFormService.create_form",
        "authorize",
    ): (
        "form.create is a workspace permission and the form does not exist yet "
        "(the id read from the body is the new form's own), so it has no access "
        "mode or grants to decide on"
    ),
    (
        "app/services/analytics_service.py",
        "AnalyticsService.check_user_can_view_analytics",
        "authorize",
    ): (
        "the workspace-level check that comes first, so a non-member never learns "
        "whether a slug exists; the slug is resolved to its form and "
        "authorize(..., form_id=link.form_id) decides on it right after"
    ),
    (
        "app/services/form_response_service.py",
        "FormResponseService.get_response_for_pdf",
        "authorize",
    ): (
        "the workspace-level response.read check that comes first; the response is "
        "resolved to its form and staff_permissions_on(user, workspace_id, "
        "response.form_id) decides on that form before anything is decrypted"
    ),
    ("app/services/api_access.py", "require_key_scope", "effective_permissions"): (
        "the key creator's workspace-level permissions for the scope, read first; "
        "the same function then calls require_key_on_form(key, scope, form_id) "
        "when it was given a form"
    ),
    (
        "app/services/authorization_service.py",
        "AuthorizationService.delivery_log_permissions",
        "effective_permissions",
    ): (
        "the workspace-level answer is the base; with a form and the switch on "
        "the same function decides on the form (form_permissions) right after"
    ),
    (
        "app/services/authorization_service.py",
        "AuthorizationService.staff_permissions_on",
        "effective_permissions",
    ): (
        "the branch for no form or the switch off, where the form-level decision "
        "is the workspace-level one by definition; with both it uses "
        "form_permissions"
    ),
    (
        "app/services/form_service.py",
        "FormService.get_form_by_version",
        "has_permission",
    ): (
        "the workspace-level 'is staff' test; while the switch is on the next "
        "statement narrows it with _can_open_as_staff(user, workspace_id, "
        "form_id), which decides on the form"
    ),
    (
        "app/services/responder_groups_service.py",
        "ResponderGroupsService.create_group",
        "authorize",
    ): (
        "members.manage is Owner/Admin-only and never granted per form, so a "
        "grant or a restricted form changes nothing; the form is only checked "
        "to belong to the workspace afterwards"
    ),
    (
        "app/services/workspace_form_service.py",
        "WorkspaceFormService.duplicate_form",
        "authorize",
    ): (
        "form.create is a workspace permission (never granted per form); the "
        "source form is decided right after with form_if_enforced(form_id): "
        "form.read, or form.edit for a template"
    ),
}


def _violations(sites: List[Site]) -> List[Site]:
    return [
        s
        for s in sites
        if s.in_form_function
        and not s.passes_form
        and (s.path, s.function, s.call) not in ALLOWED
    ]


def test_the_guard_sees_the_decision_call_sites():
    sites = all_sites()
    by_call = {name: [s for s in sites if s.call == name] for name in DECISIONS}
    # the scan really reads the services (a refactor that hides the calls from
    # it, or a moved package, fails here instead of passing for nothing)
    assert len(by_call["authorize"]) >= 80, {k: len(v) for k, v in by_call.items()}
    assert len(by_call["has_permission"]) >= 8
    assert len(by_call["effective_permissions"]) >= 8
    assert len(by_call["require_key_scope"]) >= 2
    assert len(by_call["require_key_on_form"]) >= 1
    assert len([s for s in sites if s.in_form_function and s.passes_form]) >= 55


def test_every_decision_in_a_function_about_a_form_names_the_form():
    missing = _violations(all_sites())
    assert not missing, (
        "an authorize / has_permission / effective_permissions / key check in a "
        "function that receives a form id does not pass form_id (it decides on "
        "the workspace role alone, so a restricted form is open to its members). "
        "Pass form_id (form_if_enforced(form_id) where the call looks the form up "
        "itself), or add the call to ALLOWED in "
        "tests/app/services/test_form_access_call_sites.py with the reason:\n"
        + "\n".join(
            f"  {s.path}:{s.line} {s.function} -> {s.call}" for s in missing
        )
    )


def test_every_allowed_entry_still_matches_a_call():
    live = {
        (s.path, s.function, s.call)
        for s in all_sites()
        if s.in_form_function and not s.passes_form
    }
    stale = sorted(set(ALLOWED) - live)
    assert not stale, (
        "ALLOWED entries that match no call that lacks form_id any more (remove "
        f"them): {stale}"
    )
    for key, reason in ALLOWED.items():
        assert len(reason.strip()) >= 30, f"{key}: say why"


# -- the two key surfaces ------------------------------------------------------------


def _calls_in(function) -> Set[str]:
    return {
        name
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and (name := _callee(node))
    }


def _functions(path: Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _is_decorated_with(function, owner: str, attribute: str) -> bool:
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(target, ast.Attribute)
            and target.attr == attribute
            and isinstance(target.value, ast.Name)
            and target.value.id == owner
        ):
            return True
    return False


def mcp_tools() -> List[ast.AsyncFunctionDef]:
    return [
        f
        for f in _functions(PACKAGE / "app" / "mcp" / "server.py")
        if _is_decorated_with(f, "mcp", "tool")
    ]


def test_every_mcp_tool_that_names_a_form_goes_through_require_form():
    """A tool with a ``form_id`` decides it with ``_require_form`` (the form is
    one the key's creator may open, and holds what the scope needs on it); a tool
    that names only a response decides on the response's form (``may_read`` ->
    ``key_may_use_form``) before it decrypts anything."""
    tools = mcp_tools()
    assert len(tools) >= 12, [t.name for t in tools]
    named_a_form = 0
    for tool in tools:
        parameters = _parameters(tool)
        calls = _calls_in(tool)
        if any(re.search(r"form_?ids?$", p, re.IGNORECASE) for p in parameters):
            named_a_form += 1
            assert "_require_form" in calls, (
                f"MCP tool {tool.name} takes a form_id and does not call "
                "_require_form(key, scope, form_id)"
            )
        if any(re.search(r"(response|submission)_?ids?$", p, re.IGNORECASE) for p in parameters):
            assert "key_may_use_form" in calls or "_require_form" in calls, (
                f"MCP tool {tool.name} takes a response_id and does not decide on "
                "the response's form (key_may_use_form)"
            )
    assert named_a_form >= 6


def test_every_public_api_route_with_a_form_id_is_decided_on_the_form():
    """A route whose path carries ``{form_id}`` takes the ``api_key`` dependency,
    which decides on the form before the handler reads anything; the submissions
    routes (``submissions=True``: they judge the key's own form list first) call
    ``require_key_on_form`` themselves."""
    routes = 0
    for function in _functions(PACKAGE / "app" / "public_api" / "routes.py"):
        paths = [
            node.value
            for decorator in function.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in {"get", "post", "put", "patch", "delete"}
            for node in decorator.args[:1]
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        if not any(re.search(r"\{\w*form_?ids?\}", path, re.IGNORECASE) for path in paths):
            continue
        routes += 1
        keys = [
            call
            for default in (*function.args.defaults, *function.args.kw_defaults)
            if default is not None
            for call in ast.walk(default)
            if isinstance(call, ast.Call) and _callee(call) == "api_key"
        ]
        assert keys, f"{function.name}: a {{form_id}} route without the api_key dependency"
        own = any(
            keyword.arg == "submissions"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for call in keys
            for keyword in call.keywords
        )
        if own:
            assert "require_key_on_form" in _calls_in(function), (
                f"{function.name}: a submissions route has to call "
                "require_key_on_form(key, scope, form_id) itself"
            )
    assert routes >= 11, routes


def test_the_guard_catches_a_missing_form_id(tmp_path):
    source = tmp_path / "app" / "bad.py"
    source.parent.mkdir()
    source.write_text(
        "class S:\n"
        "    async def a(self, user, workspace_id, form_id):\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id)\n"  # 3
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id, form_id=form_id)\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id, form_id)\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id, form_id=None)\n"  # 6
        "        await self._authz.has_permission(user, P.FORM_READ, workspace_id)\n"  # 7
        "        await self._authz.effective_permissions(user, workspace_id)\n"  # 8
        "        await require_key_scope(key, 'forms:read')\n"  # 9
        "        await require_key_scope(key, 'forms:read', form_id)\n"
        "        await require_key_on_form(key, 'forms:read', form_id=form_if_enforced(form_id))\n"
        "    async def workspace_level(self, user, workspace_id):\n"
        "        await self._authz.authorize(user, P.FORM_CREATE, workspace_id)\n"
        "    async def nested(self, user, workspace_id, source_form_id):\n"
        "        async def inner():\n"
        "            await self._authz.authorize(user, P.FORM_READ, workspace_id)\n"
        "        await inner()\n"
        "    async def options(self, user, workspace_id, form_id, **kw):\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id, **kw)\n"
        "    async def body(self, user, workspace_id, request):\n"
        "        ids = request.source.form_id\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id)\n"  # 22
        "    async def many(self, user, workspace_id, form_ids):\n"
        "        await self._authz.authorize(user, P.FORM_READ, workspace_id)\n"  # 24
    )
    found = {s.line: s for s in sites_in(source, tmp_path / "")}
    assert {line for line, s in found.items() if s.in_form_function and not s.passes_form} == {
        3,
        6,
        7,
        8,
        9,
        16,
        19,
        22,
        24,
    }
    assert not found[13].in_form_function
    assert found[16].function == "S.nested.inner"
