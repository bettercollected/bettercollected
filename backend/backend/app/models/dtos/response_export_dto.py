import datetime as dt
from typing import List, Optional

from camel_converter import to_camel
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.filter_queries.response_export import (
    DeletionStatusFilter,
    RespondentFilter,
    ResponseExportFilters,
)


class ResponseExportRequest(BaseModel):
    """``POST .../exports``: which columns and which responses. Everything is
    optional: no body asks for every column of every response. The filter names
    are those of the responses list."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid"
    )

    # keys from ``GET .../exports/columns``; none means every column
    columns: Optional[List[str]] = Field(default=None, max_length=1000)
    submitted_from: Optional[dt.datetime] = None
    submitted_to: Optional[dt.datetime] = None
    status: List[DeletionStatusFilter] = Field(default_factory=list, max_length=4)
    respondent: Optional[RespondentFilter] = None
    form_version: List[int] = Field(default_factory=list, max_length=50)
    search: Optional[str] = Field(default=None, max_length=320)

    @model_validator(mode="after")
    def _instants(self):
        for name in ("submitted_from", "submitted_to"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(
                    f"{to_camel(name)} needs a UTC offset, for example 2026-01-31T23:00:00Z."
                )
        if (
            self.submitted_from
            and self.submitted_to
            and self.submitted_from >= self.submitted_to
        ):
            raise ValueError("submittedFrom must be before submittedTo.")
        if any(v < 0 or v > 1_000_000 for v in self.form_version):
            raise ValueError("formVersion must be between 0 and 1000000.")
        return self

    def filters(self) -> ResponseExportFilters:
        return ResponseExportFilters(
            submitted_from=self.submitted_from,
            submitted_to=self.submitted_to,
            status=tuple(dict.fromkeys(self.status)),
            respondent=self.respondent,
            form_version=tuple(dict.fromkeys(self.form_version)),
            search=(self.search or "").strip() or None,
        )
