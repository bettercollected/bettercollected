from datetime import timedelta

from temporalio import workflow

from activities.export_as_csv import export_as_csv
from models.export_as_csv import ExportCSVParams


@workflow.defn(name="export_as_csv_workflow")
class ExportCSVWorkflow:
    @workflow.run
    async def run(self, export_csv_params: ExportCSVParams) -> str:
        return await workflow.execute_activity(export_as_csv, export_csv_params,
                                               start_to_close_timeout=timedelta(minutes=5))
