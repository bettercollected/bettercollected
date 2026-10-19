import asyncio
from typing import List
from urllib.parse import quote

from beanie import PydanticObjectId
from common.enums.plan import Plans
from fastapi_mail import MessageSchema
from pydantic import EmailStr

from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.user import UserDocument
from auth.app.services.mail_service import (
    MailService,
    one_line,
    render,
    sender_name,
    avatar_image_url,
)
from auth.app.services.stripe_service import StripeService
from auth.config import settings


class UserService:
    def __init__(self, user_repo: UserRepository, stripe_service: StripeService):
        self.user_repo = user_repo
        self.stripe_service: StripeService = stripe_service

    async def get_user_info_from_user_ids(self, user_ids: List[PydanticObjectId]):
        return await self.user_repo.get_users_by_ids(user_ids=user_ids)

    async def get_users_info_from_emails(self, emails: List[EmailStr]):
        return await self.user_repo.get_users_by_emails(emails=emails)

    async def send_mail_to_user_for_invitation(
        self,
        workspace_title: str,
        workspace_name: str,
        role: str,
        email: str,
        token: str,
        inviter_id: str,
    ):
        inviter: UserDocument = await self.user_repo.get_user_by_id(inviter_id)
        invitation_link = (
            f"{settings.CLIENT_ADMIN_URL}/{quote(workspace_name, safe='')}"
            f"/invitation/{quote(token, safe='')}"
        )
        # an inviter without a first name (e.g. signed up by email code) is
        # named by their email rather than failing the mail
        inviter_name = one_line(inviter.first_name or inviter.email) or ""
        # From and subject are this instance's; the workspace title is chosen
        # by the workspace and only shown in the body (#761)
        product = sender_name()
        message = MessageSchema(
            subject=f"You have been invited to a workspace on {product}",
            recipients=[email],
            body=render(
                "invitation_mail.html",
                product=product,
                workspace_title=one_line(workspace_title),
                role=one_line(role),
                invitation_link=invitation_link,
                inviter_name=inviter_name,
                image_url=avatar_image_url(inviter.profile_image),
                initial=inviter_name[:1].upper(),
            ),
            subtype="html",
        )
        await MailService().send_message(message)

    async def delete_user(self, user_id: PydanticObjectId):
        user = await self.user_repo.get_user_by_id(user_id=user_id)
        if user.stripe_customer_id:
            await run_sync(self.stripe_service.delete_customer, user.stripe_customer_id)
        return await self.user_repo.delete_user(user_id=user_id)

    async def upgrade_user_to_pro(self, user_id):
        return await self.user_repo.set_user_plan(user_id, Plans.PRO)


def run_sync(func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, func, *args, **kwargs)
