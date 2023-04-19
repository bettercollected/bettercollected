from typing import List

from beanie import PydanticObjectId
from fastapi_mail import MessageSchema

from auth.app.repositories.user_repository import UserRepository
from auth.app.schemas.user import UserDocument
from auth.app.services.mail_service import MailService
from auth.config import settings


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_user_info_from_user_ids(self, user_ids: List[PydanticObjectId]):
        return await UserDocument.find({"_id": {"$in": user_ids}}).to_list()

    async def send_mail_to_user_for_invitation(
        self,
        workspace_title: str,
        workspace_name: str,
        role: str,
        email: str,
        token: str,
    ):
        invitation_link = (
            settings.CLIENT_ADMIN_URL + "/" + workspace_name + "/invitation/" + token
        )
        template_body = {
            "workspace_title": workspace_title,
            "role": role,
            "invitation_link": invitation_link,
        }
        message = MessageSchema(
            subject=f"{workspace_title} invitation",
            recipients=[email],
            template_body=template_body,
            subtype="html",
        )
        mail_service = MailService(organization_name=workspace_title)
        await mail_service.send_async_mail(
            message, template_name="invitation_mail.html"
        )
