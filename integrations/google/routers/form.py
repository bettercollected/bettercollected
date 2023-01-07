from http import HTTPStatus

from common.utils.cbv import cbv
from dependencies import Container
from settings.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/google/forms")


@cbv(router=router)
class GoogleFormRouter:
    def __init__(self):
        """
        This class defines the routes for interacting with the Google forms.
        """
        super().__init__()

        # Injecting form_service dependency
        self.form_service = Container.form_service()

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_all_google_forms(self):
        """
        Retrieve a list of all google forms.

        Returns:
            A list of google forms.
        """
        return await self.form_service.get_forms()
