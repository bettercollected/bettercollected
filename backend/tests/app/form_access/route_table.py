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

from dataclasses import dataclass, replace
from typing import Callable, Dict, Optional, Tuple

from common.constants import MESSAGE_FORBIDDEN

from backend.app.services.form_access.mode import (
    PROMOTION_FROM_RESTRICTED_CODE,
    TEMPLATE_FROM_RESTRICTED_CODE,
)

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
    # the statuses an allowed member is answered with once let through, and a
    # check of the data it returns (``check(ctx, response)`` gives a problem or
    # None); both are asserted in the matrix, not only "not refused"
    # path parameters sent with a real sub-object of the matrix's world (a webhook,
    # an export, ...) instead of a made-up id: ((parameter, ctx key), ...)
    ids: Tuple[Tuple[str, str], ...] = ()
    ok: Tuple[int, ...] = ()
    check: Optional[Callable] = None
    # on a restricted form only the creator, an Owner or an Admin may (a member who
    # holds the permissions otherwise gets 403 ``template_from_restricted_form``)
    creator_only: bool = False
    # the code that refusal carries (a template's by default; copying a form to
    # another workspace has its own)
    creator_only_code: str = TEMPLATE_FROM_RESTRICTED_CODE
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


def _promotion_preview(ctx):
    # the target is the form's own workspace (a copy into it): the matrix decides
    # on the form in the path; the target side is covered by
    # tests/app/form_promotion/test_permissions.py
    return {"json": {"targetWorkspaceId": ctx["ws"]}}


def _promotion_apply(ctx):
    # a stale source ETag: every member the access decision lets through is
    # answered 412 and nothing is copied (a real copy is tested there)
    return {
        "json": {"targetWorkspaceId": ctx["ws"], "sourceEtag": '"stale"'},
        "headers": {"Idempotency-Key": "matrix"},
    }


def _promotion_targets(ctx):
    return {"params": {"targetWorkspaceId": ctx["ws"]}}


def _drill_request(ctx):
    return {
        "json": {
            "definition": {
                "v": 1,
                "cards": [{"id": "c", "kind": "bar", "dimension": {"field": "form_version"}, "measures": [{"agg": "count"}]}],
            },
            "card": "c",
            "group": "1",
        }
    }


def _view_write(ctx):
    return {
        "json": {
            "name": "Matrix view",
            "definition": {
                "v": 1,
                "cards": [{"id": "c", "kind": "tile", "measures": [{"agg": "count"}]}],
            },
        }
    }


def _view_change(ctx):
    return {"json": {"revision": 1, "name": "Matrix view"}}


def _report_query(ctx):
    return {
        "json": {
            "v": 1,
            "cards": [{"id": "c", "kind": "tile", "measures": [{"agg": "count"}]}],
        }
    }


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
        FORM, P.FORM_CREATE, P.FORM_EDIT, case="forms.as_template", creator_only=True
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
    # the audit log of one form: audit.read, which a Privacy officer keeps on a
    # restricted form (services/audit_log); a grantee Editor never holds it
    ("GET", F + "/audit-log"): route(FORM, P.AUDIT_READ, case="forms.audit_log"),
    # the same, taken out as a file: audit.read on that form, and recorded first
    ("GET", F + "/audit-log/export"): route(
        FORM, P.AUDIT_READ, case="forms.audit_log_export"
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
    # --- copying the form to another workspace (FORM_PROMOTION_ENABLED, switched on
    # in the matrix's world): form.read here, form.create in the target (the same
    # workspace in the matrix); a restricted form only for its creator, an Owner or
    # an Admin
    ("GET", F + "/spec-file"): route(
        FORM,
        P.FORM_READ,
        creator_only=True,
        creator_only_code=PROMOTION_FROM_RESTRICTED_CODE,
    ),
    ("GET", F + "/promotion/targets"): route(
        FORM, P.FORM_READ, request=_promotion_targets
    ),
    ("POST", F + "/promotion/preview"): route(
        FORM,
        P.FORM_READ,
        P.FORM_CREATE,
        request=_promotion_preview,
        creator_only=True,
        creator_only_code=PROMOTION_FROM_RESTRICTED_CODE,
    ),
    ("POST", F + "/promotion/apply"): route(
        FORM,
        P.FORM_READ,
        P.FORM_CREATE,
        request=_promotion_apply,
        creator_only=True,
        creator_only_code=PROMOTION_FROM_RESTRICTED_CODE,
    ),
    # --- reports on the form's answers (REPORTING_ENABLED, switched on in the matrix's
    # world): response.read and analytics.read on that form, in that order, so a
    # Privacy officer (analytics.read, never response.read) is refused first
    ("GET", F + "/report/fields"): route(FORM, P.RESPONSE_READ, P.ANALYTICS_READ),
    ("POST", F + "/report/query"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ, request=_report_query
    ),
    # the responses behind a group of a card (drill-down): the same gate
    ("POST", F + "/report/responses"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ, request=_drill_request
    ),
    # saved views of the report: the same gate; a view for the whole form needs form.edit on
    # top, which the matrix's private request never asks for
    ("GET", F + "/report/views"): route(FORM, P.RESPONSE_READ, P.ANALYTICS_READ),
    ("POST", F + "/report/views"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ, request=_view_write
    ),
    ("GET", F + "/report/views/{view_id}"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ
    ),
    ("PATCH", F + "/report/views/{view_id}"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ, request=_view_change
    ),
    ("DELETE", F + "/report/views/{view_id}"): route(
        FORM, P.RESPONSE_READ, P.ANALYTICS_READ
    ),
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

# What a member who is let through is answered with, per route (the statuses the
# route gives once the access decision has passed: its own success, or the check
# that comes after it for a made-up body). Asserted for every allowed member in
# the matrix, and every classified route must have an entry: a status that leaves
# this set is a change of behaviour to look at, not a pass.
OUTCOMES: Dict[Tuple[str, str], Tuple[int, ...]] = {
    # (opaque: every answer is the same 404, a real signature is read elsewhere)
    ("GET", W + "/submissions/{submission_id}/signatures/{field_id}"): (404,),
    ("GET", W + "/all-submissions"): (200,),
    ("POST", W + "/form/{form_id}/template"): (200,),
    ("GET", W + "/forms"): (200,),
    ("POST", W + "/forms/search"): (200,),
    ("DELETE", F + ""): (200,),
    ("GET", F + ""): (200,),
    ("PATCH", F + ""): (200,),
    ("GET", F + "/access"): (200,),
    ("PUT", F + "/access/mode"): (200, 403),
    ("GET", F + "/access/candidates"): (200, 403),
    ("GET", F + "/access/impact"): (200, 403),
    ("PATCH", F + "/actions"): (200,),
    ("POST", F + "/actions"): (200,),
    ("DELETE", F + "/actions/{action_id}"): (200,),
    ("GET", F + "/actions/{action_id}/reconsent"): (200,),
    ("POST", F + "/ai/chat"): (403,),
    ("GET", F + "/ai/insights"): (200,),
    ("POST", F + "/ai/insights"): (403,),
    ("PUT", F + "/ai/insights/settings"): (200,),
    ("POST", F + "/ai/proposals/{proposal_id}/accept"): (404,),
    ("POST", F + "/ai/proposals/{proposal_id}/reject"): (404,),
    ("POST", F + "/ai/review"): (403,),
    ("POST", F + "/ai/review/apply"): (200,),
    ("GET", F + "/all-submissions"): (200,),
    ("GET", F + "/report/fields"): (200,),
    ("POST", F + "/report/query"): (200,),
    ("POST", F + "/report/responses"): (200,),
    ("GET", F + "/report/views"): (200,),
    ("POST", F + "/report/views"): (201,),
    ("GET", F + "/report/views/{view_id}"): (404,),
    ("PATCH", F + "/report/views/{view_id}"): (404,),
    ("DELETE", F + "/report/views/{view_id}"): (404,),
    ("POST", F + "/duplicate"): (200,),
    ("GET", F + "/email-actions"): (200,),
    ("POST", F + "/email-actions"): (422,),
    ("GET", F + "/email-actions/deliveries"): (200,),
    ("POST", F + "/email-actions/preview"): (200,),
    ("GET", F + "/email-actions/variables"): (200,),
    ("DELETE", F + "/email-actions/{action_id}"): (404,),
    ("PATCH", F + "/email-actions/{action_id}"): (404,),
    ("POST", F + "/email-actions/{action_id}/test"): (404,),
    ("GET", F + "/exports"): (200,),
    ("POST", F + "/exports"): (202, 409, 429),
    ("GET", F + "/exports/columns"): (200,),
    ("DELETE", F + "/exports/{export_id}"): (204, 404),
    ("GET", F + "/exports/{export_id}"): (200, 404),
    ("GET", F + "/exports/{export_id}/download"): (200, 404),
    ("GET", F + "/flow-analytics"): (200,),
    ("PUT", F + "/grants"): (200, 403),
    ("DELETE", F + "/grants/{grant_id}"): (204,),
    ("DELETE", F + "/groups"): (200,),
    ("PATCH", F + "/groups/add"): (200,),
    ("GET", F + "/imports"): (200,),
    ("POST", F + "/imports"): (415,),
    ("DELETE", F + "/imports/{import_id}"): (204,),
    ("GET", F + "/imports/{import_id}"): (200,),
    ("POST", F + "/imports/{import_id}/check"): (422,),
    ("POST", F + "/imports/{import_id}/rollback"): (409,),
    ("POST", F + "/imports/{import_id}/run"): (422,),
    ("DELETE", F + "/logo"): (200,),
    ("PUT", F + "/logo"): (200,),
    ("GET", F + "/open-formulieren-export"): (200,),
    # (the matrix's form is a first-generation one, not built from pages: once the
    # access decision lets a member through, 422 ``form_not_promotable`` is the
    # answer; a form built from pages is copied in tests/app/form_promotion)
    ("GET", F + "/spec-file"): (200, 422),
    ("GET", F + "/promotion/targets"): (200,),
    ("POST", F + "/promotion/preview"): (200, 422),
    ("POST", F + "/promotion/apply"): (412, 422),
    ("POST", F + "/ops"): (428,),
    ("POST", F + "/ops/dry-run"): (422,),
    ("POST", F + "/publish"): (200,),
    ("GET", F + "/registration"): (200,),
    ("PUT", F + "/registration"): (200,),
    ("GET", F + "/registration/deliveries"): (200,),
    ("POST", F + "/registration/deliveries/{delivery_id}/retry"): (404,),
    ("POST", F + "/registration/test"): (200,),
    ("GET", F + "/registration/variables"): (200,),
    ("DELETE", F + "/response/{response_id}"): (200,),
    ("PATCH", F + "/settings"): (200,),
    ("GET", F + "/submission-paths"): (200,),
    ("GET", F + "/submissions"): (200,),
    ("PATCH", F + "/submissions/{submission_id}/answers"): (200,),
    ("POST", F + "/submissions/{submission_id}/deletion-request/close"): (200, 409),
    ("POST", F + "/submissions/{submission_id}/feedback"): (400,),
    ("PATCH", F + "/submissions/{submission_id}/internal-answers"): (400,),
    ("GET", F + "/submissions/{submission_id}/revisions"): (200,),
    ("GET", F + "/submissions/{submission_id}/revisions/{seq}"): (404,),
    ("GET", F + "/version-diff"): (422,),
    ("GET", F + "/audit-log"): (200,),
    ("GET", F + "/audit-log/export"): (200,),
    ("GET", F + "/versions"): (200,),
    ("POST", F + "/versions/{version}/restore"): (200,),
    ("GET", F + "/webhooks"): (200,),
    ("POST", F + "/webhooks"): (201,),
    ("GET", F + "/webhooks/audit"): (200,),
    ("GET", F + "/webhooks/deliveries"): (200,),
    ("GET", F + "/webhooks/variables"): (200,),
    ("DELETE", F + "/webhooks/{webhook_id}"): (204,),
    ("PATCH", F + "/webhooks/{webhook_id}"): (200,),
    ("GET", F + "/webhooks/{webhook_id}/detail"): (200,),
    ("POST", F + "/webhooks/{webhook_id}/rotate-secret"): (200,),
    ("POST", F + "/webhooks/{webhook_id}/test"): (200,),
    ("GET", W + "/responders"): (200,),
    ("GET", W + "/stats"): (200,),
    ("DELETE", W + "/submissions/{submission_id}"): (400,),
    ("GET", W + "/submissions/{submission_id}"): (200,),
    ("GET", W + "/submissions/{submission_id}/pdf"): (200,),
    ("GET", "/{workspace_name}/forms/{slug}/metrics"): (200,),
    ("GET", "/{workspace_name}/forms/{slug}/pageviews"): (200,),
    ("GET", "/{workspace_name}/forms/{slug}/stats"): (200,),
}
for _key, _route in list(ROUTES.items()):
    if _key in OUTCOMES:
        ROUTES[_key] = replace(_route, ok=OUTCOMES[_key])

def _data(**tests):
    """A check of a 200/201 answer: every named test must hold (a problem is the
    name of the first that does not)."""

    def check(ctx, response):
        for name, test in tests.items():
            try:
                if not test(ctx, response):
                    return name
            except Exception as error:  # noqa: BLE001
                return f"{name} ({type(error).__name__})"
        return None

    return check


def _id(ctx, key):
    return str(ctx[key])


# What the data of the routes that return some must say (a made-up body or an empty
# list would pass "not refused"; these do not).
CHECKS = {
    ("GET", F): _data(form=lambda c, r: r.json()["formId"] == _id(c, "form")),
    ("GET", F + "/versions"): _data(first=lambda c, r: r.json()["versions"][0]["version"] == 1),
    ("GET", F + "/audit-log"): _data(
        page=lambda c, r: isinstance(r.json()["entries"], list)
        and isinstance(r.json()["labels"], dict)
    ),
    ("GET", F + "/audit-log/export"): _data(
        # a CSV file (a byte order mark, then the header), not an error body
        file=lambda c, r: r.text.startswith("\ufeffid,event,area,at,"),
    ),
    ("GET", F + "/submissions"): _data(
        answer=lambda c, r: _id(c, "response") in r.text,
        page=lambda c, r: isinstance(r.json()["items"], list),
    ),
    ("GET", F + "/all-submissions"): _data(
        answer=lambda c, r: _id(c, "response") in r.text,
        every=lambda c, r: len(r.json()) >= 2,
    ),
    ("GET", F + "/submission-paths"): _data(list=lambda c, r: isinstance(r.json(), list)),
    ("GET", F + "/exports/columns"): _data(
        key=lambda c, r: "response_id" in {i["key"] for i in r.json()}
    ),
    ("GET", F + "/access"): _data(
        # (switched off the answer says so and lists nothing)
        mine=lambda c, r: not r.json()["enabled"]
        or "form.read" in r.json()["myPermissions"],
    ),
    ("GET", F + "/webhooks"): _data(webhook=lambda c, r: _id(c, "webhook") in r.text),
    ("POST", F + "/webhooks"): _data(secret=lambda c, r: bool(r.json()["secret"])),
    ("GET", F + "/webhooks/{webhook_id}/detail"): _data(
        id=lambda c, r: r.json()["id"] == _id(c, "webhook")
    ),
    ("POST", F + "/webhooks/{webhook_id}/rotate-secret"): _data(
        secret=lambda c, r: bool(r.json()["secret"])
    ),
    ("GET", F + "/imports"): _data(listed=lambda c, r: _id(c, "import") in r.text),
    ("GET", F + "/imports/{import_id}"): _data(
        id=lambda c, r: r.json()["id"] == _id(c, "import")
    ),
    # (a member lists their own exports only: the Owner's built one is not theirs)
    ("GET", F + "/exports"): _data(list=lambda c, r: isinstance(r.json(), list)),
    ("GET", F + "/exports/{export_id}"): _data(
        id=lambda c, r: r.json()["id"] == _id(c, "export"),
        ready=lambda c, r: r.json()["status"] == "ready",
    ),
    ("GET", F + "/exports/{export_id}/download"): _data(
        file=lambda c, r: len(r.content) > 0
    ),
    ("GET", F + "/open-formulieren-export"): _data(zip=lambda c, r: r.content[:2] == b"PK"),
    ("GET", F + "/flow-analytics"): _data(sessions=lambda c, r: "totalSessions" in r.json()),
    ("GET", W + "/submissions/{submission_id}"): _data(
        form=lambda c, r: r.json()["form"]["formId"] == _id(c, "form")
    ),
    ("GET", W + "/submissions/{submission_id}/pdf"): _data(
        pdf=lambda c, r: r.content[:4] == b"%PDF"
    ),
    # (counts only the forms the member may open, so a closed member counts none)
    ("GET", W + "/stats"): _data(
        counts=lambda c, r: {"forms", "responses", "deletionRequests"} <= set(r.json())
    ),
    ("GET", W + "/all-submissions"): _data(
        listed=lambda c, r: isinstance(r.json()["items"], list)
    ),
    ("GET", "/{workspace_name}/forms/{slug}/stats"): _data(
        views=lambda c, r: r.json()["pageviews"]["value"] == 3
    ),
    ("POST", F + "/exports"): _data(queued=lambda c, r: r.status_code == 202),
}
for _key, _check in CHECKS.items():
    ROUTES[_key] = replace(ROUTES[_key], check=_check)

# Routes sent with a real sub-object of the matrix's world (a webhook, an export, an
# import, a grant, an action) instead of a made-up id; the DELETEs consume theirs.
_REAL_OBJECTS = (
    ("/webhooks/{webhook_id}", (("webhook_id", "webhook"),)),
    ("/exports/{export_id}", (("export_id", "export"),)),
    ("/imports/{import_id}", (("import_id", "import"),)),
    ("/grants/{grant_id}", (("grant_id", "grant"),)),
    ("/actions/{action_id}", (("action_id", "action"),)),
)
for _key, _route in list(ROUTES.items()):
    for _fragment, _ids in _REAL_OBJECTS:
        if _fragment in _key[1]:
            _changes = {"ids": _ids}
            if _key[0] == "DELETE":
                _changes["destructive"] = True
            if _key[1].endswith("/download"):
                _changes["request"] = lambda ctx: {"params": {"token": ctx["export_token"]}}
            ROUTES[_key] = replace(_route, **_changes)
            break

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
