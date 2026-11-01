import calendar
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from common.ids import RecordId
from common.enums.roles import Roles
from common.models.user import User, UserResponseDto
from common.models.user import UserInfo
from common.services.http_client import HttpClient
from common.services.jwt_service import decode_with_ring
from fastapi_mail import MessageSchema
from pydantic import EmailStr

from auth.app.exceptions import HTTPException
from auth.app.repositories.user_repository import (
    UserRepository,
    clear_otp,
    consume_otp,
)
from auth.app.schemas.user import UserDocument
from auth.app.services import signin_code
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.mail_service import (
    MailService,
    is_sender_name,
    one_line,
    render,
    sender_name,
    storage_image_url,
)
from auth.app.services.mail_text import mail_locale, texts
from auth.app.services.platform_admins import roles_for
from auth.config import settings


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

    async def get_user_status(
        self, user_id: RecordId, email_verified: bool = False
    ):
        """``email_verified``: the refreshing session's claim (the backend reads
        it from the user's signed refresh token)."""
        user = await self.user_repository.get_user_by_id(user_id)
        await self.user_repository.update_last_logged_in(user_id=user_id)
        roles = roles_for(user.email, user.roles, verified=email_verified)
        return UserResponseDto(**{**user.dict(), "roles": roles})

    @staticmethod
    def get_logged_user(jwt_token: str) -> User:
        jwt_response = decode_with_ring(
            jwt_token, settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
        user = User(**jwt_response)
        return user

    async def handle_auth_callback(
        self, jwt_token: str, email_verified: bool = False
    ) -> User:
        decoded_data = decode_with_ring(
            jwt_token, settings.AUTH_JWT_SECRET, algorithms=["HS256"]
        )
        user_info = UserInfo(**decoded_data)
        # Only the backend's import-OAuth flow calls this, and it sends only the
        # signed-in user's own email (the import provider's email proves
        # nothing about who the user is, #758). So this re-issues a token for an
        # existing account and never creates one.
        user_document = await self.user_repository.get_user_by_email(user_info.email)
        if not user_document:
            raise HTTPException(
                status_code=403, content="No account for this email. Sign in first."
            )
        if not (user_document.first_name and user_document.last_name) and (
            user_info.first_name or user_info.last_name
        ):
            user_document = await self.user_repository.update_user_names(
                user_document.id,
                first_name=user_info.first_name or user_document.first_name,
                last_name=user_info.last_name or user_document.last_name,
            )
        # The re-issued token continues the backend's signed-in session for the
        # same email, so it keeps that session's proof of the email (and what
        # it grants, like a config-named platform admin's ADMIN).
        return User(
            id=str(user_document.id),
            sub=user_document.email,
            roles=roles_for(
                user_document.email, user_document.roles, verified=email_verified
            ),
            plan=user_document.plan,
            email_verified=email_verified,
        )

    async def get_basic_auth_url(
        self,
        provider: str,
        client_referer_url: str,
        creator: bool,
        prospective_pro_user: bool,
    ):
        url = await self.auth_provider_factory.get_auth_provider(
            provider
        ).get_basic_auth_url(
            client_referer_url,
            creator=creator,
            prospective_pro_user=prospective_pro_user,
        )
        return {"auth_url": url}

    async def validate_otp(self, email, otp_code) -> Optional[User]:
        """The signed-in user when ``otp_code`` is the account's pending code,
        else ``None``. Under the account's row lock: an expired code is cleared
        without comparing; a stored value that is not a hash (a plain code from
        before codes were hashed) is cleared; a match consumes the code; a
        wrong code counts a try and the last allowed one clears it."""
        now = self.get_expiry_epoch_after()
        accepted = []

        def judge(user: UserDocument) -> bool:
            if not user.otp_code or not user.otp_expiry:
                return False
            if user.otp_expiry < now:
                clear_otp(user)
                return True
            expected = signin_code.parse(user.otp_code)
            if expected is None or expected.wrong_tries >= signin_code.MAX_WRONG_TRIES:
                clear_otp(user)
                return True
            if signin_code.matches(
                expected, otp_code, str(user.id), user.otp_code_for, user.otp_expiry
            ):
                consume_otp(user)
                accepted.append(True)
                return True
            wrong_tries = expected.wrong_tries + 1
            if wrong_tries >= signin_code.MAX_WRONG_TRIES:
                clear_otp(user)
            else:
                user.otp_code = signin_code.stored(expected.digest, wrong_tries)
            return True

        user = await self.user_repository.change_otp_locked(email, judge)
        if user is None or not accepted:
            return None
        return User(
            id=str(user.id),
            sub=user.email,
            plan=user.plan,
            roles=roles_for(user.email, user.roles, verified=True),
            email_verified=True,
        )

    async def basic_auth_callback(
        self, provider: str, code: str, state: str, *args, **kwargs
    ):
        request = kwargs.get("request")
        return await self.auth_provider_factory.get_auth_provider(
            provider
        ).basic_auth_callback(code, state, request=request)

    async def send_otp_to_mail(
        self,
        receiver_mail: EmailStr,
        workspace_title: Optional[str],
        workspace_profile_image: Optional[str],
        creator: bool,
        locale: Optional[str] = None,
    ):
        otp = self.generate_otp()
        otp_expiry = self.get_expiry_epoch_after(timedelta(minutes=5))
        purpose = Roles.FORM_CREATOR if creator else Roles.FORM_RESPONDER

        account = await self.user_repository.get_user_by_email(receiver_mail)
        if account is None:
            account = await self.user_repository.save_otp_user(
                email=receiver_mail, creator=creator
            )
        # only a keyed hash is stored, bound to the account's id (signin_code);
        # the code itself goes to the mail
        await self.user_repository.set_user_otp(
            account.id,
            otp_code=signin_code.stored(
                signin_code.digest(otp, str(account.id), purpose, otp_expiry)
            ),
            otp_expiry=otp_expiry,
            otp_code_for=purpose,
        )

        # From and subject are this instance's; the workspace title is
        # caller-supplied and only shown in the body (#761)
        product = sender_name()
        title = one_line(workspace_title)
        if is_sender_name(title):
            title = None
        image_url = storage_image_url(workspace_profile_image)
        # a creator is addressed formally, a respondent informally (Dutch)
        t = texts(locale, respondent=not creator)
        subject = t["code_subject"].format(product=product)
        message = MessageSchema(
            subject=subject,
            recipients=[receiver_mail],
            body=render(
                "verification_code.html",
                t=t,
                lang=mail_locale(locale),
                subject=subject,
                product=product,
                workspace_title=title,
                otp=otp,
                image_url=image_url,
                initial=(title or product)[:1].upper(),
            ),
            subtype="html",
        )
        await MailService().send_message(message)

    def generate_otp(self):
        # secrets, never random: 36^6 codes, shaped "ABC-123"
        alphabets = string.ascii_uppercase + string.digits
        return "".join("-" if i == 3 else secrets.choice(alphabets) for i in range(7))

    def get_expiry_epoch_after(self, time_delta: timedelta = timedelta()):
        return calendar.timegm((datetime.now(timezone.utc) + time_delta).utctimetuple())
