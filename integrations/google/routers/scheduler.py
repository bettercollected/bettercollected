from http import HTTPStatus

from common.utils.cbv import cbv
from settings.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/schedulers")


@cbv(router=router)
class SchedulerRouter:
    """
    This class defines the routes for interacting with the scheduler.
    """

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_all_form_scheduler_configs(self):
        """
        Retrieve a list of all form scheduler configurations.

        Returns:
            A list of form scheduler configurations.
        """
        return []
