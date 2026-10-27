"""Download a form as an Open Formulieren import archive.

``GET /workspaces/{id}/forms/{form_id}/open-formulieren-export`` answers a
zip with the form's structure (never responses, never staff-only questions)
and the number of things that did not make the trip in the
``X-Open-Formulieren-Unmapped`` header (they are listed in the archive's
README.txt). 410 ``open_formulieren_off`` unless ``OPEN_FORMULIEREN_EXPORT``
is ``on``; see docs/open-formulieren.md.
"""

from classy_fastapi import Routable, get
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.open_formulieren_mode import refuse_open_formulieren_export
from backend.app.services.user_service import get_full_user

UNMAPPED_HEADER = "X-Open-Formulieren-Unmapped"


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/open-formulieren-export",
    tags=["Open Formulieren export"],
)
class OpenFormulierenExportRouter(Routable):
    @get("", response_class=Response, responses={200: {"content": {"application/zip": {}}}})
    async def export_form(
        self,
        workspace_id: RecordId,
        form_id: RecordId,
        # first: the switch answers before the caller or the form are looked at
        _on: None = Depends(refuse_open_formulieren_export),
        user: User = Depends(get_full_user),
    ):
        result = await container.open_formulieren_export_service().export(
            workspace_id, str(form_id), user
        )
        return Response(
            content=result.data,
            media_type="application/zip",
            headers={
                # ASCII only: the name is made from the title by export_filename
                "Content-Disposition": f'attachment; filename="{result.filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                UNMAPPED_HEADER: str(result.unmapped),
            },
        )
