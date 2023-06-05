from typing import Optional, List

from beanie import PydanticObjectId
from pydantic import EmailStr

from auth.app.schemas.user import UserDocument
from common.enums.roles import Roles


class UserRepository:
    @staticmethod
    async def get_user_by_id(user_id: PydanticObjectId):
        return await UserDocument.get(user_id)

    @staticmethod
    async def get_user_by_email(email: str) -> UserDocument:
        return await UserDocument.find_one(UserDocument.email == email)

    @staticmethod
    async def get_user_by_stripe_payment_id(stripe_payment_id: str) -> UserDocument:
        return await UserDocument.find_one(
            UserDocument.stripe_payment_id == stripe_payment_id
        )

    @staticmethod
    async def get_user_by_stripe_customer_id(stripe_customer_id: str) -> UserDocument:
        return await UserDocument.find_one(
            UserDocument.stripe_customer_id == stripe_customer_id
        )

    @staticmethod
    async def get_users_by_emails(emails: List[EmailStr]):
        return await UserDocument.find({"email": {"$in": emails}}).to_list()

    @staticmethod
    async def get_users_by_ids(user_ids: List[PydanticObjectId]):
        return await UserDocument.find({"_id": {"$in": user_ids}}).to_list()

    @staticmethod
    async def save_user(
        email: str,
        first_name: str = None,
        last_name: str = None,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
        profile_image: Optional[str] = None,
    ) -> UserDocument:
        user_document = await UserRepository.get_user_by_email(email)
        if not user_document:
            roles = [Roles.FORM_RESPONDER]
            if creator:
                roles.append(Roles.FORM_CREATOR)
            user_document = UserDocument(
                email=email,
                roles=roles,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
            )
            user_document = await user_document.save()
        if creator and Roles.FORM_CREATOR not in user_document.roles:
            user_document.roles.append(Roles.FORM_CREATOR)
            await user_document.save()
        if not (
            user_document.first_name
            and user_document.last_name
            and user_document.profile_image
        ) and (first_name or last_name or profile_image):
            user_document.first_name = (
                first_name if first_name else user_document.first_name
            )
            user_document.last_name = (
                last_name if last_name else user_document.last_name
            )
            user_document.profile_image = (
                profile_image if profile_image else user_document.profile_image
            )
            user_document = await user_document.save()
        return user_document

    @staticmethod
    async def clear_user_otp(user: UserDocument):
        user.otp_code = None
        user.otp_expiry = None
        await user.save()
