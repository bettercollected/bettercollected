from http import HTTPStatus

from common.utils.cbv import cbv
from settings.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/schedulers/forms/settings")


@cbv(router=router)
class SchedulerRouter:
    # fsc_service: FormSchedulerConfigService = Depends(get_form_scheduler_config_service)

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_all_form_scheduler_configs(self):
        return ["schedulers"]
