from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from utilities.actions import run_action
    from models.run_action_code_params import RunActionCodeParams
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="run_action_code")
async def run_action_code(run_action_code_params: RunActionCodeParams):
    async with APMAsyncHttpClient("save_preview") as client:
        return await run_action(action=run_action_code_params.action,
                                form=run_action_code_params.form,
                                response=run_action_code_params.response,
                                user_email=run_action_code_params.user_email,
                                workspace= run_action_code_params.workspace)
