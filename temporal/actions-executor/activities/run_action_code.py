from temporalio import activity, workflow

from utilities.actions import run_action

with workflow.unsafe.imports_passed_through():
    from models.run_action_code_params import RunActionCodeParams
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="run_action_code")
async def run_action_code(run_action_code_params: RunActionCodeParams):
    async with APMAsyncHttpClient("save_preview") as client:
        return await run_action(action_code=run_action_code_params.action_code, form=None, response=None)
