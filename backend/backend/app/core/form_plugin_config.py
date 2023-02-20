from typing import List, Optional, Dict, Any

from pydantic import BaseModel

from backend.app.exceptions import HTTPException
from backend.app.constants import messages
from backend.app.exceptions.provider_config_exception import (
    MultipleProviderConfigException,
)


class FormProvider(BaseModel):
    enabled: bool
    provider_name: str
    provider_url: str
    auth_callback_url: str
    type: Optional[str]
    scope: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]
    api_uri: Optional[str]
    auth_uri: Optional[str]
    token_uri: Optional[str]
    redirect_uri: Optional[str]
    revoke_uri: Optional[str]


class FormProvidersConfig:
    # Holds all the form providers that are present
    form_providers: List[FormProvider]
    # Holds only those form providers which are enabled
    current_form_providers: List[FormProvider]

    def __init__(self, form_providers: List[Dict[str, Any]]):
        self.form_providers = [FormProvider(**f) for f in form_providers]
        self.current_form_providers = [f for f in self.form_providers if f.enabled]

    def get_form_provider(self, provider_name: str) -> FormProvider:
        form_provider = list(
            filter(
                lambda f: f.provider_name == provider_name, self.current_form_providers
            )
        )
        if not form_provider:
            raise HTTPException(400, messages.provider_is_not_enabled_error)
        if len(form_provider) > 1:
            raise MultipleProviderConfigException(
                500, messages.multiple_provider_config_found
            )
        return form_provider[0]
