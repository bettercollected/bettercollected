from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.run_action_code import run_action_code
from models.run_action_code_params import RunActionCodeParams


@workflow.defn(name="run_action_code")
class RunActionCode:

    @workflow.run
    async def run(self, run_action_code_params: RunActionCodeParams) -> str:
        response = await workflow.execute_activity(run_action_code,
                                                   run_action_code_params,
                                                   schedule_to_close_timeout=timedelta(minutes=1),
                                                   retry_policy=RetryPolicy(maximum_attempts=2))
        return response
