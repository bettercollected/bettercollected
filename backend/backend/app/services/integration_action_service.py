from backend.app.models.workspace import ParameterValue
from backend.app.schemas.standard_form import FormDocument


class IntegrationActionService:

    async def add_credentials_to_form_action(self, form_id: str, action_id: str,
                                             credentials: str):
        form = await FormDocument.find_one({"form_id": form_id})
        form.secrets = {str(action_id): [ParameterValue(name='Credentials', value=credentials)]}
        await form.save()
