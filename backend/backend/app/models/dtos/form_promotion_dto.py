"""The bodies of the form promotion routes (copying a form to another
workspace, ``FORM_PROMOTION_ENABLED``)."""

from typing import Any, Dict, List, Optional

from common.ids import RecordId
from fastapi_camelcase import CamelModel
from pydantic import ConfigDict, Field


class PromotionRequest(CamelModel):
    """Where a form is copied to, and what the person ticked."""

    model_config = ConfigDict(extra="forbid")

    # the workspace the copy goes to (the caller must be a member who may create
    # forms there, or edit the one named below)
    target_workspace_id: RecordId
    # None: a new form; else the form of the target workspace whose draft is
    # replaced
    target_form_id: Optional[str] = Field(None, max_length=64)
    # copy retention, purpose, retention note, privacy link and the identity and
    # editing switches too (an existing target form keeps its own otherwise; a new
    # form always takes them)
    copy_data_protection: bool = False
    # the versions the person reviewed: the source form's and the target form's
    # (preview: optional, 412 when stale; apply: required)
    source_etag: Optional[str] = Field(None, max_length=200)
    target_etag: Optional[str] = Field(None, max_length=200)


class ApplyRequest(PromotionRequest):
    source_etag: str = Field(..., min_length=1, max_length=200)
    # the target form was changed since the last copy from here: apply anyway
    overwrite: bool = False
    # copying the data protection settings would shorten how long the target
    # keeps answers: the person confirmed it
    confirm_shorter_retention: bool = False


class PromotionTargetDto(CamelModel):
    """A form of the target workspace the caller may update."""

    form_id: str
    title: Optional[str] = None
    # it was last copied from the source form named in the request
    copied_from_source: bool = False
    published: Optional[bool] = None


class PromotionTargetsDto(CamelModel):
    items: List[PromotionTargetDto]
    # more forms match than are listed: narrow with ``q``
    more: bool = False


class PromotionApplied(CamelModel):
    form_id: str
    workspace_id: str
    created: bool
    etag: Optional[str] = None
    not_carried: Dict[str, Any] = Field(default_factory=dict)
    adjusted: Dict[str, int] = Field(default_factory=dict)
