from backend.app.models.workspace import ParameterValue
from backend.app.services.form_service import FormService


class IntegrationActionService:
    def __init__(self, form_service: FormService):
        self._form_service = form_service

    async def add_credentials_to_form_action(self, form_id: str, action_id: str,
                                             credentials: str):
        form = await self._form_service.get_form_document_by_id(form_id)
        form.secrets = {action_id: []}
        form.secrets[str(action_id)].append(ParameterValue(name="Credentials", value=credentials))
        await form.save()
