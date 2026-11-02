from http import HTTPStatus
from common.ids import RecordId

from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
)
from backend.app.exceptions import HTTPException


class FormActionsService:
    def __init__(self, form_repo: PostgresFormRepository, crypto=None):
        self.form_repo = form_repo
        # the Fernet key ring (docs/auth-key-rotation.md): a credential the actions
        # executor writes back arrives in plain and is sealed here with the
        # current key
        self.crypto = crypto

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
