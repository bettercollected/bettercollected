from fastapi_camelcase import CamelModel
from pydantic import ConfigDict, Field

# the webapp's session ids are UUIDs; page ids are field ids or sentinels
_SESSION_ID = r"^[A-Za-z0-9_-]{8,64}$"
_PAGE_ID = r"^[A-Za-z0-9_.:-]{1,64}$"


class FlowEventRequest(CamelModel):
    """One anonymous navigation step: no answers, no identity."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(pattern=_SESSION_ID)
    from_page: str = Field(pattern=_PAGE_ID)
    to_page: str = Field(pattern=_PAGE_ID)
