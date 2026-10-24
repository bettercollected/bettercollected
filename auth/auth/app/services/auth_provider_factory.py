from http import HTTPStatus

from auth.app.exceptions import HTTPException
from auth.app.services.google_auth_provider import GoogleAuthProvider
from common.enums.login_provider import LoginProvider


class AuthProviderFactory:
    def __init__(self):
        self._google_auth_provider = GoogleAuthProvider()

    def get_auth_provider(self, provider):
        if provider == LoginProvider.GOOGLE.value:
            return self._google_auth_provider

        raise HTTPException(HTTPStatus.NOT_IMPLEMENTED, "Auth provider not available")
