from pydantic.schema import timedelta
from temporalio import workflow

from activities.delete_response import delete_response
from models.delete_response import DeleteResponseParams


@workflow.defn(name="delete_response_workflow")
class DeleteResponseWorkflow:
    @workflow.run
    async def run(self, form_response_params: DeleteResponseParams):
        await workflow.execute_activity(delete_response, form_response_params,
                                        start_to_close_timeout=timedelta(minutes=5),
                                        )
