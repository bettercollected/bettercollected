"""Reports on a form's answers (``REPORTING_ENABLED``, docs/reporting.md).

Counts, averages, distributions and over-time series computed on request from a
form's stored answers, for the people who may read them. Both routes need a
signed-in member who holds ``response.read`` **and** ``analytics.read`` on the
form (a Privacy officer holds the second but never the first, so never reads
anything derived from answers); a restricted form is the 404 of an unknown form
for a member it is closed to.

Both answer 422 ``reporting_off`` while the switch is off, before the session,
a permission, a row or an answer is looked at. Every answer is ``Cache-Control:
no-store``. The query is a POST with the definition as its JSON body so that no
choice a report is about ever sits in a URL, a log or a history.
"""

from http import HTTPStatus

from classy_fastapi import Routable, delete, get, patch, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.reporting import limits
from backend.app.services.reporting.definition import error as definition_error
from backend.app.services.reporting.mode import refuse_when_off
from backend.app.services.reporting.views import INVALID_CODE as VIEW_INVALID
from backend.app.services.response_export.http import NO_STORE as FILE_HEADERS
from backend.app.services.response_export.http import attachment
from backend.app.services.user_service import get_logged_user

NO_STORE = {"Cache-Control": "no-store"}


async def _body(request: Request, cap: int = limits.DEFINITION_MAX_BYTES, code: str = "invalid_definition") -> bytes:
    """The request body, read in pieces and refused past ``cap`` bytes without
    reading the rest."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cap:
        raise _too_large(cap, code)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > cap:
            raise _too_large(cap, code)
    return bytes(data)


def _too_large(cap: int, code: str):
    return definition_error(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        code,
        f"A request here is at most {cap} bytes.",
    )


@router(
    prefix="/workspaces/{workspace_id}/forms",
    tags=["Reports"],
    # first, before the session, a permission or the body is looked at
    dependencies=[Depends(refuse_when_off)],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "response.read or analytics.read is missing (and response.export for a download)."},
        404: {"description": "No such form, or no such form for the caller."},
        413: {"description": "More responses than a report reads (too_many_rows)."},
        422: {"description": "Switched off, or the definition is not valid."},
        429: {"description": "Too many queries, or other reports are being computed."},
    },
)
class ReportRouter(Routable):
    @get("/{form_id}/report/fields")
    async def report_fields(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """What the caller may build a report from: the reportable questions
        (kind, whether it can group, which aggregates, its options) and the
        built-in dimensions. Needs ``response.read`` and ``analytics.read`` on
        the form."""
        return JSONResponse(
            await container.report_service().fields(user, workspace_id, form_id),
            headers=NO_STORE,
        )

    @post("/{form_id}/report/query")
    async def report_query(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """Run a report definition (``{v: 1, filters, tz, cards}``) over the
        form's responses. Needs ``response.read`` and ``analytics.read`` on the
        form. Answers ``{definitionHash, token, generatedAt, n, scanned, cards,
        notices}``: only counts and aggregates, never a response, an answer or an
        identity. 413 ``too_many_rows`` (with the count) above the number of
        responses a report reads; 422 with ``invalid_definition``,
        ``unknown_field``, ``field_not_reportable`` or ``op_not_allowed``."""
        body = await _body(request)
        return JSONResponse(
            await container.report_service().query(user, workspace_id, form_id, body),
            headers=NO_STORE,
        )

    @post("/{form_id}/report/responses")
    async def report_responses(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """The responses behind one group of one card (drill-down): ``{definition,
        card, group, cursor?, size?}``. Answers ``{responses: [{id, submittedAt,
        formVersion, respondent}], cursor, scanned, exhausted}``: ``exhausted`` is
        true only when the set has ended; a short page with a cursor means the scan
        budget ended and asking again from the cursor goes on. Needs
        ``response.read`` and ``analytics.read`` on the form."""
        body = await _body(request, limits.DEFINITION_MAX_BYTES + 2048)
        return JSONResponse(
            await container.report_service().responses(user, workspace_id, form_id, body),
            headers=NO_STORE,
        )

    @post("/{form_id}/report/export")
    async def report_export(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> Response:
        """One card's table as a CSV file: ``{definition, card, format: "csv"}``.
        Needs ``response.export`` as well as ``response.read`` and
        ``analytics.read`` on the form: the file is what leaves the screen. The
        figures are a query's (the same pass and limits, 413 ``too_many_rows``
        above the number of responses a report reads); the entry in the
        workspace's audit log (ids and counts only) is stored before the file is
        handed out, and the file is built in memory and never stored."""
        body = await _body(request, limits.DEFINITION_MAX_BYTES + 2048)
        file = await container.report_service().export_csv(user, workspace_id, form_id, body)
        return Response(
            content=file.content,
            media_type=file.content_type,
            headers={**FILE_HEADERS, "Content-Disposition": attachment(file.file_name)},
        )

    # ------------------------------------------------------------ saved views
    @get("/{form_id}/report/views")
    async def report_views(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """The saved views the caller may open: the form's own and their own
        private ones, each with its definition. Needs ``response.read`` and
        ``analytics.read`` on the form."""
        return JSONResponse(
            await container.report_view_service().list(user, workspace_id, form_id),
            headers=NO_STORE,
        )

    @post("/{form_id}/report/views", status_code=HTTPStatus.CREATED)
    async def report_view_create(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """Save a view: ``{name, scope?: "private" | "form", definition}``. The
        definition is validated as a query's would be. A view for the whole form
        (``scope: "form"``) needs ``form.edit``. 409 ``view_name_taken`` or
        ``view_limit``."""
        body = await _body(request, limits.VIEW_BODY_MAX_BYTES, VIEW_INVALID)
        return JSONResponse(
            await container.report_view_service().create(user, workspace_id, form_id, body),
            status_code=HTTPStatus.CREATED,
            headers=NO_STORE,
        )

    @get("/{form_id}/report/views/{view_id}")
    async def report_view(
        self,
        workspace_id: RecordId,
        form_id: str,
        view_id: str,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """One view; 404 for a missing one and for another person's private one."""
        return JSONResponse(
            await container.report_view_service().get(user, workspace_id, form_id, view_id),
            headers=NO_STORE,
        )

    @patch("/{form_id}/report/views/{view_id}")
    async def report_view_update(
        self,
        workspace_id: RecordId,
        form_id: str,
        view_id: str,
        request: Request,
        user: User = Depends(get_logged_user),
    ) -> JSONResponse:
        """Rename a view, move it between private and the form's, or replace its
        definition: ``{revision, name?, scope?, definition?}``. 409
        ``view_changed`` when ``revision`` is not the view's current one."""
        body = await _body(request, limits.VIEW_BODY_MAX_BYTES, VIEW_INVALID)
        return JSONResponse(
            await container.report_view_service().update(user, workspace_id, form_id, view_id, body),
            headers=NO_STORE,
        )

    @delete("/{form_id}/report/views/{view_id}", status_code=HTTPStatus.NO_CONTENT)
    async def report_view_delete(
        self,
        workspace_id: RecordId,
        form_id: str,
        view_id: str,
        user: User = Depends(get_logged_user),
    ) -> Response:
        """Delete a view: its owner's private one, or a view of the form (needs
        ``form.edit``; one made by someone else needs ``members.manage``)."""
        await container.report_view_service().delete(user, workspace_id, form_id, view_id)
        return Response(status_code=HTTPStatus.NO_CONTENT, headers=NO_STORE)
