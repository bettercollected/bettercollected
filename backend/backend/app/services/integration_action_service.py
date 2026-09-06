from backend.app.models.workspace import ParameterValue
from backend.app.repositories.form_repository import FormRepository


class IntegrationActionService:
    def __init__(self, form_repo: FormRepository):
        self._form_repo = form_repo

    async def add_credentials_to_form_action(
        self, form_id: str, action_id: str, credentials: str
    ):
        form = await self._form_repo.get_form_document_by_id(form_id)
        form.secrets = {
            str(action_id): [ParameterValue(name="Credentials", value=credentials)]
        }
        await self._form_repo.save_form(form)
