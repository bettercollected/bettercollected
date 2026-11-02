"""Forms named outside the path: in a body or a query, in an MCP argument.

The route matrix finds a form-scoped route by its path. A route that takes a form
id in its body or its query (a key's form list, an option source, a responder
group) never shows there. Discovery here reads the OpenAPI documents of the two
HTTP apps and the MCP server's tool schemas: a body or query field that names a
form (or forms) and is not classified below fails, naming the route and the
field. Each classified reference says what decides it and where that is tested.
"""

import re
from typing import Dict, List, Set, Tuple

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.mcp.server import mcp
from backend.app.public_api import openapi as public_openapi
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    cookies,
    create_form,
    restrict,
)

NAMED = re.compile(r"form_?ids?$", re.IGNORECASE)
# fields that contain "form" and are not a form's id (a form's text, a format, ...)
NOT_AN_ID = {
    "form_body",
    "formVersion",
    "format",
    "transformToList",
    "formCloseDate",
    "formOpenDate",
    "showOriginalForm",
    "form",  # the provider's own form, before any import
}

# (method, path) -> (the field, what decides it, where it is tested)
REFERENCES: Dict[Tuple[str, str], Tuple[str, str]] = {
    ("POST", "/integration/{integration_type}/oauth/callback"): (
        "body.form_id",
        "the callback checks the user may edit that form "
        "(IntegrationService._check_user_can_configure_form, form_if_enforced)",
        "test_write_enforcement.py (R56)",
    ),
    ("POST", "/workspaces/{workspace_id}/api-keys"): (
        "body.submissionFormIds, body.formIds",
        "security.manage (Owner/Admin) and every id must be a form of this "
        "workspace that the caller may open (APIKeyService._checked_submission_forms, "
        "_checked_list): a form of another workspace answers as one that is not there",
        "test_a_key_cannot_be_limited_to_a_form_of_another_workspace, "
        "test_the_form_list_is_checked",
    ),
    ("PATCH", "/workspaces/{workspace_id}/api-keys/{key_id}"): (
        "body.formIds",
        "security.manage (Owner/Admin), the key must be a live key of this workspace "
        "and every id a form of it that the caller may open "
        "(APIKeyService.update_key, _checked_list)",
        "test_the_form_list_is_checked, test_a_key_of_another_workspace_is_not_found",
    ),
    ("GET", "/workspaces/{workspace_id}/audit-log"): (
        "query.form_id",
        "audit.read (Owner, Admin, Privacy officer, who see every form's activity); "
        "the id only filters this workspace's rows, so another workspace's form "
        "matches nothing (AuditLogReader)",
        "test_nothing_crosses_workspaces (audit_log/test_audit_log_api.py)",
    ),
    ("GET", "/workspaces/{workspace_id}/audit-log/export"): (
        "query.form_id",
        "audit.read (Owner, Admin, Privacy officer); the id only filters this "
        "workspace's rows, exactly as in the list, so another workspace's form "
        "matches nothing (AuditLogReader.scope), and the export is recorded first",
        "test_the_export_holds_exactly_what_the_list_shows_for_each_filter "
        "(audit_log/test_export.py)",
    ),
    ("POST", "/workspaces/{workspace_id}/option-sources/preview"): (
        "body.formId, body.source.formId",
        "authorize_source: a form closed to the caller does not exist for them",
        "test_write_enforcement.py (option sources)",
    ),
    ("POST", "/workspaces/{workspace_id}/forms/{form_id}/promotion/preview"): (
        "body.targetFormId",
        "form.edit on that form in the target workspace (authorize with the form id: "
        "a form closed to the caller, or one of another workspace, is the 404 of an "
        "unknown form); a target workspace the caller is not in is a 404 too",
        "test_a_target_form_closed_to_the_caller_is_a_404 and "
        "test_a_target_form_of_another_workspace_is_no_form_of_the_target "
        "(form_promotion/test_permissions.py)",
    ),
    ("POST", "/workspaces/{workspace_id}/forms/{form_id}/promotion/apply"): (
        "body.targetFormId",
        "the same decision as the preview, made again before anything is written "
        "(FormPromotionService._target_permission)",
        "test_an_existing_target_needs_form_edit_on_it (form_promotion/test_permissions.py)",
    ),
    ("POST", "/{workspace_id}/responder-groups"): (
        "query.form_id",
        "members.manage (Owner/Admin only, never granted per form); the form "
        "must belong to the workspace",
        "test_a_responder_group_is_made_by_owners_and_admins_only",
    ),
}


def _properties(schemas: dict, schema, seen=()) -> Set[str]:
    found: Set[str] = set()
    if not isinstance(schema, dict):
        return found
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return found
        return _properties(schemas, schemas.get(name, {}), seen + (name,))
    for key, value in (schema.get("properties") or {}).items():
        found.add(key)
        found |= {f"{key}.{inner}" for inner in _properties(schemas, value, seen)}
    for key in ("allOf", "anyOf", "oneOf"):
        for part in schema.get(key, []):
            found |= _properties(schemas, part, seen)
    if "items" in schema:
        found |= _properties(schemas, schema["items"], seen)
    return found


def named_forms(document: dict, root: str) -> Dict[Tuple[str, str], Set[str]]:
    """(method, path) -> the query parameters and body fields that name a form."""
    schemas = document.get("components", {}).get("schemas", {})
    found: Dict[Tuple[str, str], Set[str]] = {}
    for path, operations in document["paths"].items():
        for method, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            names: Set[str] = set()
            for parameter in operation.get("parameters", []):
                if parameter["in"] == "query" and NAMED.search(parameter["name"]):
                    names.add("query." + parameter["name"])
            for content in (operation.get("requestBody") or {}).get("content", {}).values():
                for name in _properties(schemas, content.get("schema", {})):
                    if NAMED.search(name.split(".")[-1]):
                        names.add("body." + name)
            if names:
                found[(method.upper(), path[len(root):] if path.startswith(root) else path)] = names
    return found


def test_every_route_that_names_a_form_outside_its_path_is_classified(_initialized_app):
    root = settings.api_settings.ROOT_PATH
    rest = named_forms(_initialized_app.openapi(), root)
    # the public API's bodies are spec documents and submissions: the only form
    # they can name is an option source's (a question fed by another form's answers)
    public = {
        route: {n for n in names if not n.endswith("optionSource.formId")}
        for route, names in named_forms(public_openapi.build_openapi(), "").items()
    }
    public = {route: names for route, names in public.items() if names}
    assert not public, f"the public API names a form in a body or query: {public}"
    unclassified = sorted(set(rest) - set(REFERENCES))
    assert not unclassified, (
        "routes that take a form in the body or the query and are not classified "
        "in REFERENCES (say what decides them on the form, and test it):\n"
        + "\n".join(f"  {m} {p} {sorted(rest[(m, p)])}" for m, p in unclassified)
    )
    gone = sorted(set(REFERENCES) - set(rest))
    assert not gone, f"classified references that no longer exist: {gone}"
    for key, (field, decides, tested) in REFERENCES.items():
        assert len(decides) > 30 and tested, key


async def test_every_mcp_argument_that_names_a_form_or_a_response_is_known():
    """The MCP tools take ``form_id`` or ``response_id`` and nothing else that
    names one (not a list of forms, not a nested id): a new argument of that kind
    fails until the tool is classified for it."""
    tools = await mcp.list_tools()
    ids = re.compile(r"(form|response|submission)", re.IGNORECASE)
    unknown: List[str] = []
    for tool in tools:
        schema = tool.input_schema or {}
        for name in _properties(schema.get("$defs", {}), {"properties": schema.get("properties", {})}):
            if ids.search(name) and name not in ("form_id", "response_id"):
                unknown.append(f"{tool.name}.{name}")
    assert not unknown, f"MCP arguments that name a form or response: {unknown}"


# -- the references, decided -------------------------------------------------------------


@pytest.fixture()
async def two_forms(workspace):
    """A restricted form and an Editor and an Admin of the workspace."""
    form = await create_form(workspace, testUser)
    await restrict(workspace, form.form_id)
    editor = await add_member(workspace, "COLLABORATOR")
    admin = await add_member(workspace, "ADMIN")
    return form, editor, admin


async def test_an_api_key_cannot_feed_a_question_from_a_forms_answers_closed_or_not(
    client: AsyncClient, workspace, monkeypatch
):
    """``optionSource.formId`` in a spec sent through the public API: a key's scope
    does not say what its holder may read, so a key never points a question at
    another form's answers; a closed form and an unknown one answer alike."""
    import copy

    from tests.app.controllers.submission_cases import SPEC
    from tests.app.form_access.test_key_enforcement import _call, _token

    form = await create_form(workspace, testUser)
    await restrict(workspace, form.form_id)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    token = await _token(workspace, testUser)

    def spec_for(form_id):
        spec = copy.deepcopy(SPEC)
        meal = next(f for p in spec["pages"] for f in p["fields"] if f["id"] == "meal")
        meal.pop("choices", None)
        meal["optionSource"] = {
            "kind": "form_answers",
            "formId": str(form_id),
            "questionId": "name",
        }
        return spec

    closed = await _call(client, token, "POST", "/forms", json=spec_for(form.form_id))
    unknown = await _call(client, token, "POST", "/forms", json=spec_for(RecordId()))
    assert (closed.status_code, closed.json()) == (unknown.status_code, unknown.json())
    assert closed.status_code in (403, 422), closed.text


async def test_a_key_cannot_be_limited_to_a_form_of_another_workspace(
    client: AsyncClient, workspace, workspace_1, monkeypatch
):
    from tests.app.controllers.data import testUser1

    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    foreign = await create_form(workspace_1, testUser1)
    own = await create_form(workspace, testUser)
    url = f"{api(workspace)}/api-keys"

    async def make(form_ids):
        return await client.post(
            url,
            json={"name": "k", "scopes": ["submissions:write"], "submissionFormIds": form_ids},
            cookies=cookies(testUser),
        )

    assert (await make([str(own.form_id)])).status_code in (200, 201)
    for ids in ([str(foreign.form_id)], [str(RecordId())]):
        refused = await make(ids)
        assert refused.status_code in (400, 404, 422), (ids, refused.status_code)
    # and the answer for a foreign form is the one for an unknown form
    foreign_answer = await make([str(foreign.form_id)])
    unknown_answer = await make([str(RecordId())])
    assert (foreign_answer.status_code, foreign_answer.text) == (
        unknown_answer.status_code,
        unknown_answer.text,
    )


async def test_a_responder_group_is_made_by_owners_and_admins_only(
    client: AsyncClient, workspace, two_forms, monkeypatch
):
    """``form_id`` in the query of ``POST /{workspace_id}/responder-groups``: the
    route asks members.manage, which no grant and no restriction changes."""
    form, editor, admin = two_forms
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    url = f"/api/v1/{workspace.id}/responder-groups"
    params = {"name": "Group", "form_id": str(form.form_id)}
    refused = await client.post(url, params=params, cookies=cookies(editor))
    assert refused.status_code == 403, refused.text
    allowed = await client.post(url, params=params, cookies=cookies(admin))
    assert allowed.status_code == 200, allowed.text
    # a form of nobody's: the same refusal for the Editor, whatever the form
    again = await client.post(
        url, params={"name": "G2", "form_id": str(RecordId())}, cookies=cookies(editor)
    )
    assert (again.status_code, again.text) == (refused.status_code, refused.text)
