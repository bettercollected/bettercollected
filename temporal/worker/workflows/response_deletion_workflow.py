from pydantic.schema import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.delete_response import de
from models.ImportFormParams import ImportFormParams
from models.delete_response import DeleteResponseParams


@workflow.defn(name="delete_response_workflow")
class ImportFormWorkflow:
    @workflow.run
    async def run(self, form_response_params: DeleteResponseParams):
        await workflow.execute_activity(import_form, form_response_params, start_to_close_timeout=timedelta(minutes=5),
                                        )
