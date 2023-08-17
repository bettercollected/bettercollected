from typing import List

from beanie import PydanticObjectId
from fastapi_mail import MessageSchema
from pydantic import EmailStr

from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.user import UserDocument
from auth.app.services.mail_service import MailService
from auth.config import settings


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_user_info_from_user_ids(self, user_ids: List[PydanticObjectId]):
        return await UserRepository.get_users_by_ids(user_ids=user_ids)

    async def get_users_info_from_emails(self, emails: List[EmailStr]):
        return await UserRepository.get_users_by_emails(emails=emails)

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
            settings.CLIENT_ADMIN_URL + "/" + workspace_name + "/invitation/" + token
        )
        template_body = {
            "workspace_title": workspace_title,
            "role": role,
            "invitation_link": invitation_link,
            "inviter_name": inviter.first_name,
            "image_url": inviter.profile_image,
            "image_alternative": inviter.first_name[0],
        }
        message = MessageSchema(
            subject=f"{workspace_title} invitation",
            recipients=[email],
            template_body=template_body,
            subtype="html",
        )
        mail_service = MailService(organization_name=workspace_title)
        if inviter.profile_image:
            await mail_service.send_async_mail(
                message, template_name="invitation_mail.html"
            )
        else:
            await mail_service.send_async_mail(
                message, template_name="invitation_mail_without_image.html"
            )

    async def delete_user(self, user_id: PydanticObjectId):
        return await UserRepository.delete_user(user_id=user_id)
