from typing import Optional

from fastapi_camelcase import CamelModel


class UserFeedbackDto(CamelModel):
    reason_for_deletion: str
    feedback: Optional[str]
