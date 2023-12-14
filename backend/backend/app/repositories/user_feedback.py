from backend.app.schemas.user_feedback import UserFeedbackDocument


class UserFeedbackRepo:

    async def save_user_feedback(self, user_feedback: UserFeedbackDocument):
        return await user_feedback.save()
