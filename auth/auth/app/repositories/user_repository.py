from typing import Optional

from auth.app.schemas.user import UserDocument

from common.enums.roles import Roles


class UserRepository:
    @staticmethod
    async def get_user_by_email(email: str) -> UserDocument:
        return await UserDocument.find_one(UserDocument.email == email)

    @staticmethod
    async def save_user(
        email: str,
        first_name: str = None,
        last_name: str = None,
        otp_code: Optional[str] = None,
        otp_expiry: Optional[int] = None,
        creator: bool = True,
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
        if (not user_document.first_name or not user_document.last_name) and (
            first_name or last_name
        ):
            user_document.first_name = (
                first_name if first_name else user_document.first_name
            )
            user_document.last_name = (
                last_name if last_name else user_document.last_name
            )
            user_document = await user_document.save()
        return user_document

    @staticmethod
    async def clear_user_otp(user: UserDocument):
        user.otp_code = None
        user.otp_expiry = None
        await user.save()
