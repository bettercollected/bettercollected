from backend.app.models.workspace import ParameterValue
from backend.app.repositories.form_repository import FormRepository

CREDENTIALS = "Credentials"


class IntegrationActionService:
    def __init__(self, form_repo: FormRepository):
        self._form_repo = form_repo

    async def add_credentials_to_form_action(
        self, form_id: str, action_id: str, credentials: str
    ):
        """Store (or replace) one action's credentials on a form.

        ``form.secrets`` holds every action's secrets keyed by action id, so
        only this action's ``Credentials`` entry changes: other actions keep
        their secrets, and this action keeps any other secrets it has (#769).
        """
        form = await self._form_repo.get_form_document_by_id(form_id)
        secrets = dict(form.secrets or {})
        kept = [
            secret
            for secret in secrets.get(str(action_id)) or []
            if secret.name != CREDENTIALS
        ]
        secrets[str(action_id)] = kept + [
            ParameterValue(name=CREDENTIALS, value=credentials)
        ]
        form.secrets = secrets
        await self._form_repo.save_form(form)
