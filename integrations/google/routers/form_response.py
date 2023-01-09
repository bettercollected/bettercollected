from http import HTTPStatus

from common.utils.cbv import cbv
from dependencies import Container
from settings.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/google/submissions")


@cbv(router=router)
class GoogleFormResponseRouter:
    def __init__(self):
        """
        This class defines the routes for interacting with the Google forms.
        """

        # Injecting dependencies
        self.form_response_service = Container.form_response_service()

    @router.get("", status_code=HTTPStatus.OK)
    async def _get_all_submissions(self):
        return await self.form_response_service.get_all_submissions()

    @router.get("/{submission_id}", status_code=HTTPStatus.OK)
    async def _get_single_submission(self, submission_id: str):
        return await self.form_response_service.get_submission(submission_id)

    @router.get("/{form_id}/submissions", status_code=HTTPStatus.OK)
    async def _get_form_specific_submissions(self, form_id: str):
        return await self.form_response_service.get_form_specific_submissions(form_id)
