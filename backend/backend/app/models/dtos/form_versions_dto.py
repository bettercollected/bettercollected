import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi_camelcase import CamelModel
from pydantic import Field


class VersionAuthorDto(CamelModel):
    """Who published a version: the member's current name, never an id or an
    address. ``name`` is empty when it could not be looked up; ``former`` says
    the person is no longer a member."""

    name: Optional[str] = None
    role: Optional[str] = None
    former: bool = False


class FormVersionSummaryDto(CamelModel):
    version: int
    published_at: Optional[dt.datetime] = None
    published_by: Optional[VersionAuthorDto] = None
    # the newest published version: what respondents see now
    current: bool = False


class FormDraftStateDto(CamelModel):
    """The draft as the versions page needs it: the stamp a restore must
    send back, and whether the draft holds work not yet published."""

    updated_at: Optional[dt.datetime] = None
    has_unpublished_changes: bool = False


class FormVersionListDto(CamelModel):
    versions: List[FormVersionSummaryDto]
    # older versions exist than the newest LIST_LIMIT listed (each is still
    # reachable by number)
    truncated: bool = False
    draft: Optional[FormDraftStateDto] = None


class VersionChangeDto(CamelModel):
    kind: str
    scope: str
    ref: Optional[str] = None
    title: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class VersionCompareDto(CamelModel):
    # "1", "2", ... or "draft"
    from_version: str
    to_version: str
    changed: bool
    entries: List[VersionChangeDto]
    truncated: bool = False


class RestoreVersionRequest(CamelModel):
    # the draft's updatedAt the page was showing (409 form_changed when the
    # draft moved on since)
    expected_updated_at: dt.datetime
    # confirm that unpublished changes in the draft are replaced
    replace_draft: bool = False


class RestoreVersionResponse(CamelModel):
    restored_version: int
    updated_at: Optional[dt.datetime] = None
