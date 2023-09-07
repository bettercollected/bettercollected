from pydantic.schema import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.import_form import import_form
from models.ImportFormParams import ImportFormParams


@workflow.defn(name="delete_response_workflow")
class ImportFormWorkflow:
    @workflow.run
    async def run(self, import_form_param: ImportFormParams):
        await workflow.execute_activity(import_form, import_form_param, start_to_close_timeout=timedelta(minutes=5),
                                        retry_policy=RetryPolicy(maximum_attempts=1))
