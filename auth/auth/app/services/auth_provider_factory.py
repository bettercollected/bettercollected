from http import HTTPStatus

from auth.app.exceptions import HTTPException
from auth.app.services.google_auth_provider import GoogleAuthProvider
from auth.app.services.typeform_auth_provider import TypeformAuthProvider


class AuthProviderFactory:
    def __init__(self):
        self._google_auth_provider = GoogleAuthProvider()
        self._typeform_auth_provider = TypeformAuthProvider()

    def get_auth_provider(self, provider):
        if provider == "google":
            return self._google_auth_provider
        if provider == "typeform":
            return self._typeform_auth_provider

        raise HTTPException(HTTPStatus.NOT_IMPLEMENTED, "Auth provider not available")
