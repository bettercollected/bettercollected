from backend.app.models.dtos.user_feedback import UserFeedbackDto
from backend.app.repositories.user_feedback import UserFeedbackRepo
from backend.app.schemas.user_feedback import UserFeedbackDocument


class UserFeedbackService:
    def __init__(self, user_feedback_repo: UserFeedbackRepo):
        self.user_feedback_repo = user_feedback_repo

    async def save_user_feedback(self, user_feedback: UserFeedbackDto):
        await self.user_feedback_repo.save_user_feedback(
            UserFeedbackDocument(**user_feedback.dict())
        )
