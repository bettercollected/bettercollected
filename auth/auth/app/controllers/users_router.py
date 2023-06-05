from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, delete
from fastapi import Query
from pydantic import EmailStr
from starlette.background import BackgroundTasks

from auth.app.container import container
from auth.app.exceptions import HTTPException
from auth.app.router import router


@router(prefix="/users", tags=["Users"])
class UserRouter(Routable):
    def __init__(self, user_service=container.user_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_service = user_service

    @get("")
    async def get_details_of_users_with_ids(
        self,
        user_ids: List[PydanticObjectId] = Query(None),
        emails: List[EmailStr] = Query(None),
    ):
        if not (bool(user_ids) ^ bool(emails)):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, content="Only one query is allowed"
            )
        if user_ids:
            users_info = await self.user_service.get_user_info_from_user_ids(
                user_ids=user_ids
            )
            return {"users_info": users_info}
        users_info = await self.user_service.get_users_info_from_emails(emails=emails)
        return {"users_info": users_info}

    @get("/invite/send/mail")
    async def send_mail_to_user_for_invitation(
        self,
        workspace_title: str,
        workspace_name: str,
        role: str,
        email: str,
        token: str,
        inviter_id: str,
        background_tasks: BackgroundTasks,
    ):
        background_tasks.add_task(
            self.user_service.send_mail_to_user_for_invitation,
            workspace_title=workspace_title,
            workspace_name=workspace_name,
            role=role,
            email=email,
            token=token,
            inviter_id=inviter_id,
        )

        return "Mail sent successfully!!"

    @delete("/{user_id}")
    async def delete_user(self, user_id: PydanticObjectId):
        return await self.user_service.delete_user(user_id=user_id)
