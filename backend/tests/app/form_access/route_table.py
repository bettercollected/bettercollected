"""The classification of every route that is about a form (or resolves one), for
the route matrix (``test_route_matrix.py``).

A route is *form-scoped* when its path carries a form id, a custom URL (slug), a
response or submission id, or sits on a form-bound collection (``/forms``,
``/submissions``, ``/responders``, ``/stats``, ``/template(s)``, the import
tables). The matrix walks the application's route table and fails, naming the
route, for every form-scoped route that is not in ``ROUTES`` (decided on the
form, with the permission it asks) or in ``EXEMPT`` (with the reason no
form-level decision applies). A listed route that no longer exists fails too.

Every entry is written from what the route does for a member, not from what the
service imports: ``chain`` is the permissions the route asks, in the order it asks
them (the first one the member lacks decides the answer: 404 for a member the
form is closed to when their role holds it, 403 otherwise).
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from common.constants import MESSAGE_FORBIDDEN

from backend.app.models.enum.permission import Permission

P = Permission
NOT_AUTHORIZED = "You are not authorized to perform this action."
W = "/workspaces/{workspace_id}"
F = W + "/forms/{form_id}"

FORM = "form"  # decided on the form named in the path
LIST = "list"  # a workspace-level list narrowed to the forms the member may open
RESPONSE = "response"  # a response id in the path: decided on the response's form


@dataclass(frozen=True)
class Route:
    kind: str
    chain: Tuple[Permission, ...]
    # the row of tests/app/controllers/test_permission_matrix.py whose request
    # (body, query, headers) this route is sent with, or a request written here
    case: Optional[str] = None
    request: Optional[Callable[[dict], dict]] = None
    # which id the "same as an unknown one" comparison swaps: the form (default)
    # or the response
    ghost: str = "form"
    # the request consumes or changes what other requests act on (a form, a
    # response): the matrix sends it once, last, for the first member who may
    destructive: bool = False
    # the route does not exist while form-level access is off (it answers 422 to
    # everyone, before any permission is looked at)
    needs_switch: bool = False
    # a delivery log: ``audit.read`` opens it, except on a restricted form the
    # member may not edit (services/authorization_service.py)
    delivery_log: bool = False
    # the key of the matrix's response ids the path is built with ("requested":
    # the one that has a deletion request)
    response_key: str = "response"
    # what a member the route refuses (the role lacks the permission) is answered
    # with: the standard 403, unless the route is one a respondent shares with
    # staff (a non-staff caller who is not the respondent)
    refused_status: int = 403
    refused_body: object = MESSAGE_FORBIDDEN
    # every refusal of the route is the same 404 as a response that is not there
    # (the signature image: it says nothing of which responses or questions exist),
    # so the matrix cannot tell a refused member from one who may read: it only
    # compares a closed member with an unknown id; a dedicated test reads a real
    # signature
    opaque: bool = False
    # a route staff share with the response's own respondent: a member the form
    # is closed to is no staff there, so whatever their role holds, the
    # respondent rule answers (404 for a response that is not theirs)
    respondent_rule: bool = False
    # what a member the form is closed to gets when it is not 404: the route asks
    # ``has_permission`` first and falls through to a permission their role lacks
    # (the answer is still the one an unknown form gives)
    closed_status: int = 404
    # set by the matrix from the table key
    method: str = ""


@dataclass(frozen=True)
class Exempt:
    reason: str


def route(kind, *chain, **options) -> Route:
    return Route(kind, tuple(chain), **options)


def _json_body(ctx):
    return {"json": {}}


def _mode_request(ctx):
    return {"json": {"mode": ctx["mode"]}}


def _impact_request(ctx):
    return {"params": {"mode": "restricted"}}


def _grant_request(ctx):
    # a member who is no principal of the matrix; a Viewer grant never changes
    # what another call of the matrix is expected to answer
    return {"json": {"subjectType": "user", "subjectId": ctx["removable"], "role": "VIEWER"}}


def _webhook(ctx):
    return {"json": {"url": "https://hooks.voorbeeld.example/matrix", "fields": []}}


def _webhook_update(ctx):
    return {"json": {"enabled": False}}


def _email_action(ctx):
    template = {"subject": "Thanks", "body": "We received your answers."}
    return {"json": {"name": "Matrix", "en": template, "nl": template}}


def _email_action_update(ctx):
    return {"json": {"enabled": False}}


def _email_preview(ctx):
    return {"json": {"language": "en", "subject": "Hello", "body": "Hello"}}


def _registration(ctx):
    return {"json": {"enabled": False}}


def _export(ctx):
    return {"json": {}}


# --------------------------------------------------------------------------------
# Decided on a form (the member's permissions on THAT form, not on the workspace)
# --------------------------------------------------------------------------------
ROUTES: Dict[Tuple[str, str], Route] = {
    # --- the form itself
    ("GET", F): route(FORM, P.FORM_READ, case="forms.read.draft"),
    ("PATCH", F): route(FORM, P.FORM_EDIT, case="forms.update"),
    ("DELETE", F): route(FORM, P.FORM_DELETE, case="forms.delete", destructive=True),
    ("POST", F + "/duplicate"): route(
        FORM, P.FORM_CREATE, P.FORM_READ, case="forms.duplicate"
    ),
    ("POST", W + "/form/{form_id}/template"): route(
        FORM, P.FORM_CREATE, P.FORM_EDIT, case="forms.as_template"
    ),
    ("POST", F + "/publish"): route(FORM, P.FORM_EDIT, case="forms.publish"),
    ("PATCH", F + "/settings"): route(FORM, P.FORM_EDIT, case="forms.settings"),
    ("PUT", F + "/logo"): route(FORM, P.FORM_EDIT, case="forms.logo.upload"),
    ("DELETE", F + "/logo"): route(FORM, P.FORM_EDIT, case="forms.logo.remove"),
    ("PATCH", F + "/groups/add"): route(FORM, P.FORM_EDIT, case="forms.groups.add"),
    ("DELETE", F + "/groups"): route(FORM, P.FORM_EDIT, case="forms.groups.remove"),
    # --- versions and the editor
    ("GET", F + "/versions"): route(FORM, P.FORM_READ, case="forms.versions.list"),
    ("GET", F + "/version-diff"): route(FORM, P.FORM_READ, case="forms.versions.diff"),
    ("POST", F + "/versions/{version}/restore"): route(
        FORM, P.FORM_EDIT, case="forms.versions.restore"
    ),
    ("POST", F + "/ops"): route(FORM, P.FORM_EDIT, case="forms.ops.save"),
    ("POST", F + "/ops/dry-run"): route(FORM, P.FORM_EDIT, case="spec.dry_run"),
    ("GET", F + "/open-formulieren-export"): route(
        FORM, P.FORM_READ, case="forms.open_formulieren_export"
    ),
    # --- who may open the form (the access routes: form.share on that form)
    ("GET", F + "/access"): route(FORM, P.FORM_READ),
    ("PUT", F + "/access/mode"): route(
        FORM, P.FORM_SHARE, request=_mode_request, needs_switch=True
    ),
    ("GET", F + "/access/candidates"): route(FORM, P.FORM_SHARE, needs_switch=True),
    ("GET", F + "/access/impact"): route(
        FORM, P.FORM_SHARE, request=_impact_request, needs_switch=True
    ),
    ("PUT", F + "/grants"): route(
        FORM, P.FORM_SHARE, request=_grant_request, needs_switch=True
    ),
    ("DELETE", F + "/grants/{grant_id}"): route(FORM, P.FORM_SHARE, needs_switch=True),
    # --- actions
    ("POST", F + "/actions"): route(
        FORM, P.FORM_EDIT, P.RESPONSE_EXPORT, case="forms.actions.add"
    ),
    ("PATCH", F + "/actions"): route(FORM, P.FORM_EDIT, case="forms.actions.update"),
    ("DELETE", F + "/actions/{action_id}"): route(
        FORM, P.FORM_EDIT, case="forms.actions.remove"
    ),
    ("GET", F + "/actions/{action_id}/reconsent"): route(FORM, P.FORM_EDIT),
    # --- AI on a form
    ("POST", F + "/ai/chat"): route(FORM, P.FORM_EDIT, case="ai.chat"),
    ("POST", F + "/ai/review"): route(FORM, P.FORM_EDIT, case="ai.review"),
    ("POST", F + "/ai/review/apply"): route(
        FORM,
        P.FORM_EDIT,
        request=lambda ctx: {
            "json": {"ops": [{"op": "update_form_info", "title": "Matrix"}]}
        },
    ),
    ("POST", F + "/ai/proposals/{proposal_id}/accept"): route(
        FORM, P.FORM_EDIT, case="ai.proposal.accept"
    ),
    ("POST", F + "/ai/proposals/{proposal_id}/reject"): route(
        FORM, P.FORM_EDIT, case="ai.proposal.reject"
    ),
    ("GET", F + "/ai/insights"): route(FORM, P.RESPONSE_READ, case="ai.insights.get"),
    ("POST", F + "/ai/insights"): route(
        FORM, P.RESPONSE_READ, case="ai.insights.generate"
    ),
    ("PUT", F + "/ai/insights/settings"): route(
        FORM, P.AI_MANAGE, case="ai.insights.settings"
    ),
    # --- answers
    ("GET", F + "/submissions"): route(FORM, P.RESPONSE_READ, case="responses.form"),
    ("GET", F + "/all-submissions"): route(
        FORM, P.RESPONSE_EXPORT, case="responses.form.all"
    ),
    ("GET", F + "/submission-paths"): route(
        FORM, P.RESPONSE_READ, case="responses.form.paths"
    ),
    ("PATCH", F + "/submissions/{submission_id}/internal-answers"): route(
        FORM, P.RESPONSE_ANNOTATE, case="responses.internal_answers"
    ),
    ("PATCH", F + "/submissions/{submission_id}/answers"): route(
        FORM, P.RESPONSE_EDIT, case="responses.answers.edit"
    ),
    ("GET", F + "/submissions/{submission_id}/revisions"): route(
        FORM, P.RESPONSE_READ, case="responses.revisions.list"
    ),
    ("GET", F + "/submissions/{submission_id}/revisions/{seq}"): route(
        FORM, P.RESPONSE_READ, case="responses.revisions.values"
    ),
    ("POST", F + "/submissions/{submission_id}/feedback"): route(
        FORM, P.RESPONSE_ANNOTATE, case="responses.feedback"
    ),
    ("POST", F + "/submissions/{submission_id}/deletion-request/close"): route(
        FORM,
        P.PRIVACY_MANAGE,
        case="responses.deletion_request.close",
        response_key="requested",
    ),
    ("DELETE", F + "/response/{response_id}"): route(
        FORM,
        P.RESPONSE_DELETE,
        case="responses.delete",
        destructive=True,
        closed_status=403,
    ),
    ("GET", F + "/flow-analytics"): route(
        FORM, P.ANALYTICS_READ, case="responses.flow_analytics"
    ),
    # --- exports (the file of every answer: response.export on that form)
    ("GET", F + "/exports"): route(FORM, P.RESPONSE_EXPORT, case="responses.form.export.list"),
    ("POST", F + "/exports"): route(
        FORM, P.RESPONSE_EXPORT, request=_export, case="responses.form.export"
    ),
    ("GET", F + "/exports/columns"): route(
        FORM, P.RESPONSE_EXPORT, case="responses.form.export.columns"
    ),
    ("GET", F + "/exports/{export_id}"): route(
        FORM, P.RESPONSE_EXPORT, case="responses.form.export.status"
    ),
    ("DELETE", F + "/exports/{export_id}"): route(
        FORM, P.RESPONSE_EXPORT, case="responses.form.export.discard"
    ),
    ("GET", F + "/exports/{export_id}/download"): route(
        FORM, P.RESPONSE_EXPORT, case="responses.form.export.download"
    ),
    # --- response imports (Owner/Admin only: never granted per form)
    ("GET", F + "/imports"): route(FORM, P.RESPONSE_IMPORT),
    ("POST", F + "/imports"): route(FORM, P.RESPONSE_IMPORT),
    ("GET", F + "/imports/{import_id}"): route(FORM, P.RESPONSE_IMPORT),
    ("DELETE", F + "/imports/{import_id}"): route(FORM, P.RESPONSE_IMPORT),
    ("POST", F + "/imports/{import_id}/check"): route(
        FORM, P.RESPONSE_IMPORT, request=_json_body
    ),
    ("POST", F + "/imports/{import_id}/run"): route(
        FORM, P.RESPONSE_IMPORT, request=_json_body
    ),
    ("POST", F + "/imports/{import_id}/rollback"): route(
        FORM, P.RESPONSE_IMPORT, request=_json_body
    ),
    # --- webhooks (Owner/Admin: they send answers to a third party)
    ("GET", F + "/webhooks"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/webhooks"): route(FORM, P.WORKSPACE_MANAGE, request=_webhook),
    ("GET", F + "/webhooks/variables"): route(FORM, P.WORKSPACE_MANAGE),
    ("GET", F + "/webhooks/{webhook_id}/detail"): route(FORM, P.WORKSPACE_MANAGE),
    ("PATCH", F + "/webhooks/{webhook_id}"): route(
        FORM, P.WORKSPACE_MANAGE, request=_webhook_update
    ),
    ("DELETE", F + "/webhooks/{webhook_id}"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/webhooks/{webhook_id}/rotate-secret"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/webhooks/{webhook_id}/test"): route(FORM, P.WORKSPACE_MANAGE),
    ("GET", F + "/webhooks/deliveries"): route(
        FORM, P.FORM_EDIT, delivery_log=True
    ),
    ("GET", F + "/webhooks/audit"): route(FORM, P.FORM_EDIT, delivery_log=True),
    # --- email actions
    ("GET", F + "/email-actions"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/email-actions"): route(
        FORM, P.WORKSPACE_MANAGE, request=_email_action
    ),
    ("GET", F + "/email-actions/variables"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/email-actions/preview"): route(
        FORM, P.WORKSPACE_MANAGE, request=_email_preview
    ),
    ("PATCH", F + "/email-actions/{action_id}"): route(
        FORM, P.WORKSPACE_MANAGE, request=_email_action_update
    ),
    ("DELETE", F + "/email-actions/{action_id}"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/email-actions/{action_id}/test"): route(FORM, P.WORKSPACE_MANAGE),
    ("GET", F + "/email-actions/deliveries"): route(
        FORM, P.FORM_EDIT, delivery_log=True
    ),
    # --- registration (a form's hand-over to a service)
    ("GET", F + "/registration"): route(FORM, P.FORM_READ),
    ("PUT", F + "/registration"): route(
        FORM, P.WORKSPACE_MANAGE, request=_registration
    ),
    ("GET", F + "/registration/variables"): route(FORM, P.WORKSPACE_MANAGE),
    ("POST", F + "/registration/test"): route(FORM, P.WORKSPACE_MANAGE),
    ("GET", F + "/registration/deliveries"): route(FORM, P.RESPONSE_READ),
    ("POST", F + "/registration/deliveries/{delivery_id}/retry"): route(FORM, P.FORM_EDIT),
    # --- a response by its id (the response's form decides)
    ("GET", W + "/submissions/{submission_id}"): route(
        RESPONSE,
        P.RESPONSE_READ,
        case="responses.one",
        ghost="response",
        respondent_rule=True,
        refused_body=NOT_AUTHORIZED,
    ),
    ("GET", W + "/submissions/{submission_id}/pdf"): route(
        RESPONSE, P.RESPONSE_READ, case="responses.one.pdf", ghost="response"
    ),
    ("GET", W + "/submissions/{submission_id}/signatures/{field_id}"): route(
        RESPONSE,
        P.RESPONSE_READ,
        ghost="response",
        opaque=True,
        respondent_rule=True,
    ),
    ("DELETE", W + "/submissions/{submission_id}"): route(
        RESPONSE,
        P.PRIVACY_MANAGE,
        case="responses.one.request_deletion",
        ghost="response",
        respondent_rule=True,
        # it puts a deletion request on a response: sent after the routes that
        # read or delete responses, on the one the response routes do not delete
        destructive=True,
        response_key="requested",
        refused_body=NOT_AUTHORIZED,
    ),
    # --- analytics by the form's custom URL
    ("GET", "/{workspace_name}/forms/{slug}/stats"): route(
        FORM, P.ANALYTICS_READ, case="analytics.umami_stats", ghost="slug"
    ),
    ("GET", "/{workspace_name}/forms/{slug}/pageviews"): route(
        FORM,
        P.ANALYTICS_READ,
        request=lambda ctx: {
            "params": {"start_at": 1, "end_at": 2, "unit": "day", "timezone": "UTC"}
        },
        ghost="slug",
    ),
    ("GET", "/{workspace_name}/forms/{slug}/metrics"): route(
        FORM,
        P.ANALYTICS_READ,
        request=lambda ctx: {"params": {"start_at": 1, "end_at": 2, "type": "url"}},
        ghost="slug",
    ),
    # --- lists: narrowed to the forms the member may open, before count and page
    ("GET", W + "/forms"): route(LIST, P.FORM_READ, case="forms.list"),
    ("POST", W + "/forms/search"): route(LIST, P.FORM_READ, case="forms.search"),
    ("GET", W + "/stats"): route(LIST, P.ANALYTICS_READ, case="workspace.stats"),
    ("GET", W + "/all-submissions"): route(
        LIST, P.RESPONSE_READ, case="responses.workspace"
    ),
    ("GET", W + "/responders"): route(LIST, P.PRIVACY_MANAGE, case="responders.list"),
}

# --------------------------------------------------------------------------------
# Form-scoped by path, and no form-level decision applies (with the reason)
# --------------------------------------------------------------------------------
RESPONDENT = (
    "a respondent route: it answers anyone who may fill the published form in; "
    "restricting a form is about the team, never about who may answer it"
)
NO_FORM_YET = "no form exists yet: it creates one, or checks one's text, at workspace level (form.create or form.edit)"
INTERNAL = "internal job route: the shared job key (TEMPORAL_API_KEY), not a signed-in person"
TEMPLATE_LIBRARY = (
    "the workspace template library: a template is a deliberate copy into the "
    "library, with no form link and no access mode; making one from a form is "
    "decided on that form (POST /form/{form_id}/template)"
)
IMPORT_DOCUMENT = (
    "an import document of the person who started it (creating a form from a file): "
    "no form of the workspace exists until it is finished; workspace-level "
    "form.create, the document is the creator's own"
)
OWN = "the caller's own submissions or their receipt number: the respondent rule, not staff access"

EXEMPT: Dict[Tuple[str, str], Exempt] = {
    # respondent
    ("POST", F + "/response"): Exempt(RESPONDENT),
    ("PATCH", F + "/response/{response_id}"): Exempt(
        RESPONDENT + " (the respondent's own response)"
    ),
    ("POST", F + "/address-lookup"): Exempt(RESPONDENT),
    ("GET", F + "/options/{field_id}"): Exempt(RESPONDENT),
    ("POST", F + "/flow-events"): Exempt(RESPONDENT + " (anonymous navigation steps)"),
    ("PUT", F + "/drafts"): Exempt(RESPONDENT + " (a respondent's draft)"),
    ("POST", F + "/drafts/discard"): Exempt(RESPONDENT + " (a respondent's draft)"),
    ("POST", F + "/drafts/link"): Exempt(RESPONDENT + " (a respondent's draft)"),
    ("POST", F + "/drafts/mine"): Exempt(RESPONDENT + " (a respondent's draft)"),
    ("POST", F + "/drafts/open"): Exempt(RESPONDENT + " (a respondent's draft)"),
    ("GET", F + "/versions/{version}"): Exempt(
        "the published read of a version, shared with the public (the respondent's "
        "view); a member the form is closed to gets exactly the public view, staff "
        "(Owner, Admin, grantee, a role on an open form) the builder's view "
        "(FormService.get_form_by_version); asserted by "
        "test_a_closed_member_reads_a_version_as_the_public_does"
    ),
    ("GET", W + "/submissions"): Exempt(OWN),
    ("GET", W + "/submissions/by-uuid/{submission_uuid}"): Exempt(OWN),
    ("DELETE", W + "/submissions/by-uuid/{submission_uuid}"): Exempt(OWN),
    # internal
    ("PATCH", F + "/action/{action_id}/update"): Exempt(INTERNAL),
    ("POST", "/temporal/delete/submissions/{submission_id}"): Exempt(INTERNAL),
    (
        "POST",
        "/temporal" + F + "/actions/{action_id}/runs/{response_id}/context",
    ): Exempt(INTERNAL),
    (
        "PATCH",
        "/temporal" + F + "/actions/{action_id}/runs/{response_id}/secrets",
    ): Exempt(INTERNAL),
    ("POST", "/temporal" + F + "/copy-recipient"): Exempt(
        INTERNAL + "; the recipient rule is applied inside (copy_recipient.py)"
    ),
    # workspace level
    ("POST", W + "/forms"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/ai"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/ai/build"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/ai/outline"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/import/{provider}"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/pattern/check"): Exempt(NO_FORM_YET),
    ("POST", W + "/forms/validate"): Exempt(NO_FORM_YET),
    ("GET", W + "/form-imports"): Exempt(IMPORT_DOCUMENT),
    ("POST", W + "/form-imports"): Exempt(IMPORT_DOCUMENT),
    ("GET", W + "/form-imports/ai"): Exempt(IMPORT_DOCUMENT),
    ("GET", W + "/form-imports/{import_id}"): Exempt(IMPORT_DOCUMENT),
    ("GET", W + "/form-imports/{import_id}/pages/{number}"): Exempt(IMPORT_DOCUMENT),
    ("GET", W + "/form-imports/{import_id}/review"): Exempt(IMPORT_DOCUMENT),
    ("POST", W + "/open-formulieren-imports"): Exempt(IMPORT_DOCUMENT),
    ("GET", W + "/open-formulieren-imports/{import_id}"): Exempt(IMPORT_DOCUMENT),
    ("POST", W + "/open-formulieren-imports/{import_id}/review"): Exempt(IMPORT_DOCUMENT),
    ("PATCH", W + "/responders"): Exempt(
        "data subjects of the workspace (privacy.manage, Owner/Admin and Privacy officer): "
        "a tag on a person, not on a form"
    ),
    ("GET", W + "/responders/tags"): Exempt("the workspace's responder tags: no form"),
    ("POST", W + "/responders/tags"): Exempt("the workspace's responder tags: no form"),
    # templates
    ("GET", "/templates"): Exempt(TEMPLATE_LIBRARY),
    ("GET", "/templates/{template_id}"): Exempt(TEMPLATE_LIBRARY),
    ("PATCH", "/template/{template_id}/preview"): Exempt(TEMPLATE_LIBRARY),
    ("POST", W + "/template"): Exempt(TEMPLATE_LIBRARY),
    ("DELETE", W + "/template/{template_id}"): Exempt(TEMPLATE_LIBRARY),
    ("PATCH", W + "/template/{template_id}"): Exempt(TEMPLATE_LIBRARY),
    ("POST", W + "/template/{template_id}"): Exempt(TEMPLATE_LIBRARY),
    ("POST", W + "/template/{template_id}/import"): Exempt(TEMPLATE_LIBRARY),
    ("PATCH", W + "/template/{template_id}/settings"): Exempt(TEMPLATE_LIBRARY),
}


# -- which routes the matrix is bound to classify -------------------------------------
FORM_PARAMETERS = {"form_id", "slug", "response_id", "submission_id", "submission_uuid"}
FORM_COLLECTIONS = {
    "forms",
    "form",
    "submissions",
    "all-submissions",
    "responders",
    "stats",
    "form-imports",
    "open-formulieren-imports",
    "template",
    "templates",
}
# routes that never touch a form of the workspace, however their path reads
OUT_OF_SCOPE_ROOTS = {"{provider}"}  # the form-provider plugin proxy (Google, ...): the
# provider's forms, before any import


def is_form_scoped(path: str) -> bool:
    """Whether a route's path (with its ``/api/v1`` prefix) is about a form."""
    import re

    segments = [s for s in path.split("/") if s][2:]  # after api / v1
    if not segments or segments[0] in OUT_OF_SCOPE_ROOTS:
        return False
    parameters = set(re.findall(r"\{(\w+)", path))
    first = segments[0]
    if first == "workspaces" and len(segments) > 1 and segments[1] == "{workspace_id}":
        rest = segments[2:]
    elif first in ("{workspace_id}", "{workspace_name}"):
        rest = segments[1:]
    elif first in ("templates", "template", "temporal"):
        rest = segments
    else:
        return False
    return bool(parameters & FORM_PARAMETERS) or bool(rest and rest[0] in FORM_COLLECTIONS)
