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

from classy_fastapi import Routable, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.reporting import limits
from backend.app.services.reporting.definition import error as definition_error
from backend.app.services.reporting.mode import refuse_when_off
from backend.app.services.user_service import get_logged_user

NO_STORE = {"Cache-Control": "no-store"}


async def _body(request: Request) -> bytes:
    """The request body, read in pieces and refused past the definition's size
    cap without reading the rest."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limits.DEFINITION_MAX_BYTES:
        raise _too_large()
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limits.DEFINITION_MAX_BYTES:
            raise _too_large()
    return bytes(data)


def _too_large():
    return definition_error(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "invalid_definition",
        f"A definition is at most {limits.DEFINITION_MAX_BYTES} bytes.",
    )


@router(
    prefix="/workspaces/{workspace_id}/forms",
    tags=["Reports"],
    # first, before the session, a permission or the body is looked at
    dependencies=[Depends(refuse_when_off)],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "response.read or analytics.read is missing."},
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
