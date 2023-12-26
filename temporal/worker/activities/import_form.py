from temporalio import activity, workflow

from models.import_forms_params import ImportFormParams
from settings.application import settings

with workflow.unsafe.imports_passed_through():
    from wrappers.apm_wrapper import APMAsyncHttpClient


@activity.defn(name="import_form")
async def import_form(import_form_params: ImportFormParams):
    async with APMAsyncHttpClient("import_form") as client:
        headers = {"api-key": settings.api_key}
        response = await client.post(
            url=settings.server_url
                + f"/temporal/import/{import_form_params.workspace_id}/form/{import_form_params.form_id}",
            headers=headers
        )
