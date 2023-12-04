from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from models.run_action_code_params import RunActionCodeParams
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="run_action_code")
async def run_action_code(run_action_code_params: RunActionCodeParams):
    async with APMAsyncHttpClient("save_preview") as client:
        log_string = []

        def log(message: str):
            log_string.append(str(message))

        try:
            exec(
                run_action_code_params.action_code,
                {
                    "log": log
                }
            )
        except Exception as e:
            log("Exception: " + str(e))

        return "\n".join(log_string)
