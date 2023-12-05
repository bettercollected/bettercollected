from temporalio import activity, workflow
from temporalio.exceptions import FailureError

from models.save_preview_params import SavePreviewParams

with workflow.unsafe.imports_passed_through():
    import asyncio
    from settings.application import settings
    from wrappers.apm_wrapper import APMAsyncHttpClient
    from wrappers.thread_pool_executor import thread_pool_executor
    from activities.get_preview_image import get_preview_image


@activity.defn(name="save_preview")
async def save_preview(save_preview_params: SavePreviewParams):
    async with APMAsyncHttpClient("save_preview") as client:
        get_image_task = asyncio.get_event_loop().run_in_executor(thread_pool_executor, get_preview_image,
                                                                  save_preview_params)
        image_file = await get_image_task
        headers = {"api-key": settings.api_key}
        url = settings.server_url + f"/template/{save_preview_params.template_id}/preview"
        files = {"preview_image": ("preview_image.png", image_file, "image/png")}
        response = await client.patch(url, files=files, headers=headers, timeout=60)

        if response.status_code != 200:
            raise FailureError("Preview Image Patch not successful")
