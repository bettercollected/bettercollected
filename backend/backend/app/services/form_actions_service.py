from loguru import logger
from http import HTTPStatus
from common.ids import RecordId

from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
)
from backend.app.exceptions import HTTPException
from cryptography.fernet import InvalidToken


class FormActionsService:
    def __init__(self, form_repo: PostgresFormRepository, crypto=None):
        self.form_repo = form_repo
        # the Fernet key ring (docs/auth-key-rotation.md): a secret the actions
        # executor writes back is sealed with the executor's own copy of the key,
        # so it is opened here and sealed again with the current key
        self.crypto = crypto

    def _resealed(self, form_id, action_id, payload):
        """``payload`` with its value sealed by this service's current key.
        A value no key of the ring opens is refused (422) and logged by ids."""
        if self.crypto is None:
            return payload
        try:
            plain = self.crypto.decrypt(payload.value)
        except (InvalidToken, TypeError, ValueError):
            logger.warning(
                "form secret refused: not sealed with a key of the ring "
                "(form {} action {})",
                form_id,
                action_id,
            )
            raise HTTPException(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "The secret is not sealed with this deployment's key.",
            )
        return payload.model_copy(update={"value": self.crypto.encrypt(plain)})

    async def update_run_secret(self, form_id: RecordId, action_id: RecordId, payload):
        """Replace one secret of one action on the form with the plain value the
        executor refreshed, sealed here with this service's current key. 404 for
        a form whose action is not switched on (the caller has checked that the
        run belongs to the form)."""
        form = await self.form_repo.get_form_by_id(form_id)
        belongs = form is not None and any(
            str(configured.id) == str(action_id) and configured.enabled
            for configured in (form.actions or {}).get("on_submit", [])
        )
        if not belongs:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Action not found in this form.")
        if self.crypto is None:
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE, "The backend cannot seal secrets."
            )
        sealed = payload.model_copy(
            update={"value": self.crypto.encrypt(payload.value)}
        )
        return await self.form_repo.update_form_actions(
            form_id=form_id, action_id=action_id, form=form, payload=sealed
        )

    async def update_form_secrets(
        self, form_id: RecordId, action_id: RecordId, payload
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
            payload = self._resealed(form_id, action_id, payload)
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
