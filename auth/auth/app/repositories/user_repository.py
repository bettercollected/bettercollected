import datetime
from typing import Optional, List

from beanie import PydanticObjectId
from common.enums.roles import Roles
from pydantic import EmailStr

from auth.app.schemas.user import UserDocument


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
    async def save_otp_user(
        email: str,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
    ) -> UserDocument:
        user_document = await UserRepository.get_user_by_email(email)
        if not user_document:
            otp_code_for = Roles.FORM_RESPONDER
            if creator:
                otp_code_for = Roles.FORM_CREATOR
            user_document = UserDocument(
                email=email,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
                otp_code_for=otp_code_for,
            )
            user_document = await user_document.save()
        if creator and Roles.FORM_CREATOR not in user_document.otp_code_for:
            user_document.otp_code_for = Roles.FORM_CREATOR
            await user_document.save()
        return user_document

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
        roles = [Roles.FORM_RESPONDER]
        if creator:
            roles.append(Roles.FORM_CREATOR)
        if not user_document:
            user_document = UserDocument(
                email=email,
                roles=roles,
                otp_code=otp_code,
                otp_expiry=otp_expiry,
            )
        if user_document.roles:
            if creator and Roles.FORM_CREATOR not in user_document.roles:
                user_document.roles.append(Roles.FORM_CREATOR)
        else:
            user_document.roles = roles
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
        return await user_document.save()

    @staticmethod
    async def clear_user_otp(user: UserDocument):
        user_roles = [Roles.FORM_RESPONDER]
        if user.otp_code_for == Roles.FORM_CREATOR:
            user_roles.append(Roles.FORM_CREATOR)
        await UserDocument.find_one(UserDocument.id == user.id).update(
            {
                "$addToSet": {"roles": {"$each": user_roles}},
                "$unset": {"otp_code": "", "otp_expiry": "", "otp_code_for": ""},
            }
        )

    @staticmethod
    async def delete_user(user_id: PydanticObjectId):
        return await UserDocument.find({"_id": user_id}).delete()

    @staticmethod
    async def update_last_logged_in(user_id: PydanticObjectId):
        user_document = await UserDocument.find_one(UserDocument.id == user_id)
        user_document.last_logged_in = datetime.datetime.utcnow()
        return await user_document.save()
