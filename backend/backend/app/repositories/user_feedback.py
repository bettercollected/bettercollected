from backend.app.schemas.user_feedback import UserFeedbackDocument
from common.db.routing import write_op


class UserFeedbackRepo:
    @write_op
    async def save_user_feedback(self, user_feedback: UserFeedbackDocument):
        return await user_feedback.save()
