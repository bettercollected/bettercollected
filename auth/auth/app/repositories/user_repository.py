from auth.app.models.user import UserDocument
from common.enums.roles import Roles


class UserRepository:
    @staticmethod
    async def get_user_by_email(email: str) -> UserDocument:
        return await UserDocument.find_one(UserDocument.email == email)

    @staticmethod
    async def save_user(email: str) -> UserDocument:
        user_document = await UserRepository.get_user_by_email(email)
        if not user_document:
            user_document = UserDocument(
                email=email, roles=[Roles.FORM_CREATOR, Roles.FORM_RESPONDER]
            )
            user_document = await user_document.save()
        return user_document
