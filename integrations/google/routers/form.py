from http import HTTPStatus

from common.utils.cbv import cbv
from common.utils.router import CustomAPIRouter
from dependencies import Container
from settings import settings

router = CustomAPIRouter(prefix=settings.api_settings.root_path + "/google/forms")


@cbv(router=router)
class GoogleFormRouter:
    def __init__(self):
        """
        This class defines the routes for interacting with the Google forms.
        """

        # Injecting dependencies
        self.form_service = Container.form_service()

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_all_google_forms(self):
        return await self.form_service.get_forms()

    @router.get("/{form_id}", status_code=HTTPStatus.OK)
    async def _get_single_google_form(self, form_id: str):
        return await self.form_service.get_form(form_id)
