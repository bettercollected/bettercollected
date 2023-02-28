import calendar
from datetime import timedelta, datetime

import jwt
from fastapi_mail import MessageSchema
from pydantic import EmailStr
import string
import secrets

from auth.app.exceptions import HTTPException
from auth.app.models.user import UserDocument
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.mail_service import MailService
from auth.config import settings
from common.enums.roles import Roles
from common.models.user import User
from common.models.user import UserInfo
from common.services.http_client import HttpClient
from common.utils.asyncio_run import asyncio_run


class AuthService:
    def __init__(
            self,
            auth_provider_factory: AuthProviderFactory,
            user_repository: UserRepository,
            http_client: HttpClient,
    ):
        self.auth_provider_factory = auth_provider_factory
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

    async def get_basic_auth_url(self, provider: str, client_referer_url: str):
        url = await self.auth_provider_factory.get_auth_provider(
            provider
        ).get_basic_auth_url(client_referer_url)
        return {"auth_url": url}

    async def validate_otp(self, email, otp_code):
        try:
            user = await self.user_repository.get_user_by_email(email)
            if user and user.otp_code and user.otp_expiry:
                if user.otp_code != otp_code:
                    raise HTTPException(status_code=400, content="Error Invalid Verification code.")
                if user.otp_expiry < self.get_expiry_epoch_after():
                    raise HTTPException(status_code=400,
                                        content="Error Verification code is expired. Please request for new code.")
                await UserRepository.clear_user_otp(user)
                return User(id=str(user.id), sub=user.email, username=user.username, roles=user.roles)
            else:
                raise HTTPException(status_code=404, content="Error user not found.")
        except HTTPException as error:
            return None

    async def basic_auth_callback(
            self, provider: str, code: str, state: str, *args, **kwargs
    ):
        request = kwargs.get("request")
        return await self.auth_provider_factory.get_auth_provider(
            provider
        ).basic_auth_callback(code, state, request=request)

    def send_code_to_user_for_workspace_sync(
            self, receiver_mail: EmailStr, workspace_title: str
    ):
        asyncio_run(
            self.send_otp_to_mail(
                receiver_mail=receiver_mail, workspace_title=workspace_title
            )
        )

    async def send_otp_to_mail(self, receiver_mail: EmailStr, workspace_title: str):
        otp = self.generate_otp()
        otp_expiry = self.get_expiry_epoch_after(timedelta(minutes=5))

        existing_user = await self.user_repository.get_user_by_email(receiver_mail)
        if existing_user:
            existing_user.otp_code = otp
            existing_user.otp_expiry = otp_expiry
            await existing_user.save()
        else:
            await self.user_repository.save_user(
                email=receiver_mail, otp_code=otp, otp_expiry=otp_expiry
            )

        template_body = {"sender": workspace_title, "otp": otp}
        message = MessageSchema(
            subject=f"{workspace_title} identity verification code",
            recipients=[receiver_mail],
            template_body=template_body,
            subtype="html",
        )
        mail_service = MailService(organization_name=workspace_title)
        await mail_service.send_async_mail(message)

    def generate_otp(self):
        alphabets = string.ascii_uppercase + string.digits
        return "".join("-" if i == 3 else secrets.choice(alphabets) for i in range(7))

    def get_expiry_epoch_after(self, time_delta: timedelta = timedelta()):
        return calendar.timegm((datetime.utcnow() + time_delta).utctimetuple())
