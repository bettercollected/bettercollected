from typing import Optional

from fastapi_camelcase import CamelModel


class DeletionRequestsStats(CamelModel):
    total: Optional[int] = 0
    pending: Optional[int] = 0
    success: Optional[int] = 0


class WorkspaceStatsDto(CamelModel):
    forms: Optional[int] = 0
    responses: Optional[int] = 0
    deletion_requests: Optional[DeletionRequestsStats] = DeletionRequestsStats()
