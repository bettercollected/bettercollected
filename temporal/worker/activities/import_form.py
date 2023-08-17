from temporalio import activity, workflow

from models.ImportFormParams import ImportFormParams
from settings.application import settings

with workflow.unsafe.imports_passed_through():
    import requests


@activity.defn(name="import_form")
async def import_form(import_form_params: ImportFormParams):
    headers = {"api_key": settings.api_key}
    response = requests.post(
        url=settings.server_url
            + f"/temporal/import/{import_form_params.workspace_id}/form/{import_form_params.form_id}",
        headers=headers
    )
