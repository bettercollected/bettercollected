from temporalio import workflow

from models.run_action_code_params import RunActionCodeParams


@workflow.defn(name="run_action_code")
class RunActionCode:

    @workflow.run
    async def run(self, run_action_code_params: RunActionCodeParams):
        pass
