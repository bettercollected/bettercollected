from temporalio import activity, workflow

from models.delete_response import DeleteResponseParams
from settings.application import settings

with workflow.unsafe.imports_passed_through():
    from wrappers.APMWrapper import APMAsyncHttpClient


@activity.defn(name="delete_response")
async def delete_response(delete_response_params: DeleteResponseParams):
    async with APMAsyncHttpClient("delete_response") as client:
        headers = {"api-key": settings.api_key}
        response = await client.post(
            url=settings.server_url
                + f"/temporal/delete/submissions/{delete_response_params.response_id}",
            headers=headers
        )
