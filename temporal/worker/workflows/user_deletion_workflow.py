from datetime import timedelta

from temporalio import workflow

from activities.delete_user import delete_user
from models.user_tokens import UserTokens


@workflow.defn(name="delete_user_workflow")
class DeleteUserWorkflow:
    @workflow.run
    async def run(self, user_token: UserTokens) -> str:
        await workflow.execute_activity(delete_user, user_token, schedule_to_close_timeout=timedelta(minutes=5))
        return "Done"
