from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from activities.save_preview import save_preview
from models.SavePreviewParams import SavePreviewParams


@workflow.defn(name="save_template_preview")
class SaveTemplatePreview:

    @workflow.run
    async def run(self, save_template_params: SavePreviewParams):
        await workflow.execute_activity(save_preview, save_template_params,
                                        schedule_to_close_timeout=timedelta(minutes=2),
                                        retry_policy=RetryPolicy(maximum_attempts=2))
