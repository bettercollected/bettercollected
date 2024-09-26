from loguru import logger
from http import HTTPStatus
from beanie import PydanticObjectId

from backend.app.repositories.form_repository import FormRepository
from backend.app.exceptions import HTTPException


class FormActionsService:
    def __init__(self, form_repo: FormRepository):
        self.form_repo = form_repo

    async def update_form_secrets(
        self, form_id: PydanticObjectId, action_id: PydanticObjectId, payload
    ):
        form = await self.form_repo.get_form_by_id(form_id)
        if not form:
            logger.info(f"No form found with this form_id {form_id}")
            raise HTTPException(
                HTTPStatus.NOT_FOUND, f"No form found with this form_id {form_id}"
            )

        # extracting the actions id from form
        actions = form.actions["on_submit"]

        # checking if the action_id exists in the form
        action = next((action for action in actions if action.id == action_id), None)

        if action:
            return await self.form_repo.update_form_actions(
                form_id=form_id, action_id=action_id, form=form, payload=payload
            )

        else:
            # Raise an HTTPException if the action_id is not present
            logger.info(f"Action with ID {action_id} not found in form {form_id}")
            raise HTTPException(
                HTTPStatus.NOT_FOUND,
                f"Action with ID {action_id} not found in form {form_id}",
            )
