import calendar
from datetime import timedelta, datetime

import jwt

from auth.app.models.user import UserDocument
from auth.app.repositories.provider_repository import ProviderRepository
from auth.app.repositories.user_repository import UserRepository
from auth.config import settings
from common.enums.roles import Roles
from common.models.user import User
from common.models.user import UserInfo, OAuthState
from common.services.http_client import HttpClient


class AuthService:
    def __init__(
            self,
            provider_repository: ProviderRepository,
            user_repository: UserRepository,
            http_client: HttpClient,
    ):
        self.provider_repository = provider_repository
        self.user_repository = user_repository
        self.http_client = http_client

    @staticmethod
    def get_logged_user(jwt_token: str) -> User:
        jwt_response = jwt.decode(
            jwt_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
        user = User(**jwt_response)
        return user

    async def handle_auth_callback(self, jwt_token: str) -> User:
        decoded_data = jwt.decode(
            jwt_token, key=settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
        user_info = UserInfo(**decoded_data)
        user_document = await self.user_repository.get_user_by_email(user_info.email)
        if not user_document:
            user_document = UserDocument(
                email=user_info.email, roles=[Roles.FORM_RESPONDER, Roles.FORM_CREATOR]
            )
            await user_document.save()
        return User(
            id=str(user_document.id),
            sub=user_document.email,
            username=user_document.username,
            roles=user_document.roles,
            services=user_document.services,
        )
