from backend.app.services.form_response_service import FormResponseService
from backend.app.services.temporal_service import TemporalService


class FormSchedular:
    """Work the background jobs call back into through ``/temporal``: today only
    the deletion of a response whose retention period has run out."""

    def __init__(
        self,
        temporal_service: TemporalService,
        form_response_service: FormResponseService,
    ):
        self.temporal_service = temporal_service
        self.form_response_service = form_response_service

    async def delete_response(self, submission_id: str):
        response = await self.form_response_service.delete_response(
            response_id=submission_id
        )
        await self.temporal_service.delete_response_delete_schedule(
            response_id=submission_id
        )
        return response
