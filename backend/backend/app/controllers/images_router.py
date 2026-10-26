"""Images served from, or copied into, our own storage
(``services/image_service.py``)."""

from common.ids import RecordId
from classy_fastapi import Routable, get, post
from common.models.user import User
from fastapi import Depends
from fastapi_camelcase import CamelModel
from pydantic import Field
from starlette.requests import Request
from starlette.responses import RedirectResponse

from backend.app.container import container
from backend.app.router import router
from backend.app.services.image_urls import MAX_IMAGE_URL_LENGTH
from backend.app.services.user_service import get_logged_user
from backend.app.utils.client_ip import request_client_ip

# our copy never changes under its name; a day keeps a respondent's browser
# from asking again on every page while letting the cache be rebuilt
REDIRECT_HEADERS = {
    "Cache-Control": "public, max-age=86400",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class ImageImportRequest(CamelModel):
    url: str = Field(..., max_length=MAX_IMAGE_URL_LENGTH)


class ImageImportResponse(CamelModel):
    url: str


@router(prefix="", tags=["Images"])
class ImagesRouter(Routable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._images = container.image_service()

    @get("/images/unsplash/{photo_path:path}", include_in_schema=False)
    async def unsplash_image(self, photo_path: str, request: Request):
        """An Unsplash photo, served from our copy: respondents never contact
        Unsplash. Only a photo path and the sizing parameters w, h, q, fit,
        fm, crop and auto."""
        url = await self._images.serve_unsplash(
            photo_path,
            request.query_params.multi_items(),
            request_client_ip(request),
        )
        return RedirectResponse(url, status_code=302, headers=REDIRECT_HEADERS)

    @post(
        "/workspaces/{workspace_id}/images/import",
        response_model=ImageImportResponse,
    )
    async def import_image(
        self,
        workspace_id: RecordId,
        body: ImageImportRequest,
        user: User = Depends(get_logged_user),
    ) -> ImageImportResponse:
        """Copy the image at an address into our storage and return our
        address for it (``form.edit``)."""
        url = await self._images.import_image(workspace_id, body.url, user)
        return ImageImportResponse(url=url)
