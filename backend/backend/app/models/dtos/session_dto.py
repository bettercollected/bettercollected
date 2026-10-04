import datetime as dt
from typing import Optional

from fastapi_camelcase import CamelModel

from backend.app.schemas.session import SessionDocument


class SessionDto(CamelModel):
    """One of the signed-in user's sessions, as the account settings list it."""

    id: str
    created_at: Optional[dt.datetime] = None
    last_refreshed_at: Optional[dt.datetime] = None
    expires_at: Optional[dt.datetime] = None
    user_agent: Optional[str] = None
    current: bool = False

    @classmethod
    def of(cls, session: SessionDocument, current_sid: Optional[str]) -> "SessionDto":
        return cls(
            id=str(session.id),
            created_at=session.created_at,
            last_refreshed_at=session.last_refreshed_at,
            expires_at=session.expires_at,
            user_agent=session.user_agent,
            current=str(session.id) == current_sid,
        )
