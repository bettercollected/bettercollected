from datetime import timedelta

from temporalio import workflow

from activities.delete_user import delete_user


@workflow.defn(name="delete_user_workflow")
class DeleteUserWorkflow:
    @workflow.run
    async def run(self, user_token: str) -> str:
        await workflow.execute_activity(delete_user, user_token, start_to_close_timeout=timedelta(minutes=5))
        return "Done"
