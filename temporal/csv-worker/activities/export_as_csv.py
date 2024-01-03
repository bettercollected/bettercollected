from temporalio import activity, workflow

from models.export_as_csv import ExportCSVParams

with workflow.unsafe.imports_passed_through():
    from utilities.execute_csv_conversion import execute_csv_conversion
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="export_as_csv")
async def export_as_csv(export_as_csv_params: ExportCSVParams):
    async with APMAsyncHttpClient("export_as_csv") as client:
        return await execute_csv_conversion(form=export_as_csv_params.form,
                                            unconverted_responses=export_as_csv_params.responses)
