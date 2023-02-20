import calendar
from datetime import timedelta, datetime

import jwt

from auth.app.models.user import UserDocument
from auth.app.repositories.credentials_repository import CredentialRepository
from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.config import settings
from common.enums.roles import Roles
from common.models.user import User, Token, Credential
from common.models.user import UserInfo, OAuthState
from common.services.http_client import HttpClient


class AuthService:

    def __init__(self,
                 provider_repository: ProviderRepository,
                 user_repository: UserRepository,
                 credential_repository: CredentialRepository,
                 http_client: HttpClient
                 ):
        self.provider_repository = provider_repository
        self.user_repository = user_repository
        self.credential_repository = credential_repository
        self.http_client = http_client

    @staticmethod
    def get_logged_user(jwt_token: str) -> User:
        jwt_response = jwt.decode(jwt_token,
                                  key=settings.JWT_SECRET,
                                  algorithms=["HS256"]
                                  )
        user = User(**jwt_response)
        return user

    async def get_credential(self, *, email, provider) -> Credential:
        credential = await self.credential_repository.get_credential(email=email, provider=provider)
        return Credential(**credential)

    async def get_basic_auth_url(self,
                                 provider_name: str,
                                 client_referer_url: str) -> str:
        provider = await self.provider_repository.get_provider(provider_name)
        auth_redirection_url = await self.http_client.get(
            provider.basic_auth_url,
            headers={'referer': client_referer_url})
        return auth_redirection_url

    async def get_oauth_url(self,
                            provider_name: str,
                            oauth_state: OAuthState
                            ):
        # TODO implement with interface instead
        # TODO Merge with plugin and some configuration provider to share providers url
        provider = await self.provider_repository.get_provider(provider_name)
        oauth_state.auth_server_redirect_uri = settings.AUTH_REDIRECT_URI
        oauth_redirection_url = await self.http_client.get(
            provider.oauth_url,
            params=oauth_state.dict()
        )
        return oauth_redirection_url

    # TODO : Refactor this long function
    async def handle_auth_callback(self, jwt_token: str):
        decoded_token = jwt.decode(jwt_token,
                                   key=settings.JWT_SECRET,
                                   algorithms=["HS256"]
                                   )
        user_info = UserInfo(**decoded_token["user_info"])
        oauth_state = OAuthState(**decoded_token["oauth_state"])
        user_document = await self.user_repository.get_user_by_email(user_info.email)

        if not user_document:
            user_document = UserDocument(
                email=user_info.email,
                roles=[Roles.FORM_RESPONDER, Roles.FORM_CREATOR])
            await user_document.save()

        await self.credential_repository.save_credentials(user_info)
        token = jwt.encode(
            {
                "user": User(
                    id=str(user_document.id),
                    sub=user_document.email,
                    username=user_document.username,
                    roles=user_document.roles,
                    services=user_document.services
                ).dict(),
            },
            settings.JWT_SECRET
        )

        await self.http_client.get(oauth_state.backend_auth_redirect_uri,
                                   params={"jwt_token": token}
                                   )


def get_expiry_epoch_after(time_delta: timedelta = timedelta()):
    return calendar.timegm((datetime.utcnow() + time_delta).utctimetuple())
