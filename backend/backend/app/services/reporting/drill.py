"""Drill-down: the responses behind one group of one card.

A page of ``{id, submittedAt, formVersion, respondent}`` (``id``: the response id) for the responses that
met a definition's filters (the list's plaintext ones and the conditions on
answers) and fell in one group of one of its cards. Not an answer, an address or
a name leaves: the person opens a response on its own page, where the usual checks
apply. The pass is the report's (keyset on ``(created_at, id)``, decrypt, test, drop),
stopped when the page is full or ``limits.DRILL_SCAN_MAX`` responses were read.

The cursor says where the pass stands (the part of the scope, the time and the id
of the last response read). It holds no secret and gives no access: every read is
still scoped to the workspace and form of the request, so a cursor made up by hand
only starts the pass somewhere else in a form the caller may already read.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from http import HTTPStatus
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.repositories.postgres.report_queries import Cursor
from backend.app.services.reporting import limits
from backend.app.services.reporting.definition import error, invalid

_ID = re.compile(r"^[0-9a-f]{24}$")


class DrillRequest(BaseModel):
    """``definition``: the report's (filters, conditions, cards); ``card`` and
    ``group``: which group of which card; ``cursor`` and ``size``: the page."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=to_camel)

    definition: Dict[str, Any]
    card: str = Field(min_length=1, max_length=limits.CARD_ID_MAX)
    group: str = Field(min_length=1, max_length=limits.CLAUSE_VALUE_MAX)
    cursor: Optional[str] = Field(default=None, max_length=512)
    size: int = Field(default=limits.DRILL_PAGE_DEFAULT, ge=1, le=limits.DRILL_PAGE_MAX)


def parse(body: bytes) -> DrillRequest:
    """The request, or 422 ``invalid_definition`` naming where it went wrong,
    never what was sent."""
    if len(body) > limits.DEFINITION_MAX_BYTES + 2048:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_definition",
            f"A request here is at most {limits.DEFINITION_MAX_BYTES + 2048} bytes.",
        )
    try:
        return DrillRequest.model_validate_json(body)
    except ValidationError as problem:
        first = problem.errors(include_url=False, include_context=False, include_input=False)[0]
        where = ".".join(str(part) for part in first["loc"]) or "body"
        raise invalid(f"{where}: {first['msg']}") from None


def encode_cursor(cursor: Cursor) -> str:
    moment = cursor.created_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    raw = json.dumps({"p": cursor.phase, "t": moment.isoformat(), "i": cursor.id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(value: Optional[str]) -> Optional[Cursor]:
    """The cursor a page ended with, or 422 for anything else."""
    if value is None:
        return None
    try:
        raw = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        phase, moment, row_id = raw["p"], dt.datetime.fromisoformat(raw["t"]), raw["i"]
        if phase not in (0, 1) or moment.tzinfo is None or not _ID.match(row_id):
            raise ValueError("cursor")
        return Cursor(phase=phase, created_at=moment, id=row_id)
    except (ValueError, KeyError, TypeError):
        raise invalid("cursor: not a cursor this report gave") from None


def row_dto(row) -> Dict[str, Any]:
    return {
        # what the response's page is opened by (its stored id when it has no response id)
        "id": row.response_id or row.id,
        "submittedAt": row.created_at.isoformat() if row.created_at else None,
        "formVersion": row.form_version,
        "respondent": "anonymous" if row.anonymous else "known",
    }
