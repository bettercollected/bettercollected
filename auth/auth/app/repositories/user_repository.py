from auth.app.models.user import UserDocument


class UserRepository:

    @staticmethod
    async def get_user_by_email(email: str) -> UserDocument:
        return await UserDocument.find_one_by_args(UserDocument.email == email)
