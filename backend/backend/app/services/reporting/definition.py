"""The report definition: one JSON document, filters plus cards, and its strict
validation against what the caller may report on.

Shape (version 1; camelCase on the wire)::

    {"v": 1,
     "filters": {"submittedFrom": ISO, "submittedTo": ISO,
                 "status": ["none"|"pending"|"declined"|"success"],
                 "respondent": "anonymous"|"known", "formVersion": [int]},
     "tz": "Europe/Amsterdam",
     "cards": [{"id": "...", "kind": "tile|bar|donut|line|table",
                "dimension": null | {"field": "q:<question id>" | a built-in,
                                     "bucket": "day|week|month|year"},
                "measures": [{"agg": "count|avg|sum|min|max", "field": "q:<id>"}],
                "title": "..."}]}

A definition holds ids, option ids, numbers and dates, never text a respondent
wrote: a field is a question id from the catalogue or a built-in dimension; a
filter is a date, a number, an enum. Anything else is refused (extra keys
included), with the codes ``invalid_definition``, ``unknown_field``,
``field_not_reportable`` and ``op_not_allowed``. A question the caller may not
use (``policy.ReportFieldPolicy``) is refused exactly as a question that does
not exist, so the answer never tells the two apart.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from decimal import Decimal
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from camel_converter import to_camel
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from backend.app.exceptions import HTTPException
from backend.app.models.filter_queries.response_list import (
    DeletionStatusFilter,
    RespondentFilter,
    ResponseListFilters,
)
from backend.app.services.reporting import limits
from backend.app.services.reporting.catalogue import (
    ALL_OPS,
    CALCULATED,
    CHOICE,
    CHOICES,
    COUNT,
    CURRENCY,
    DATE,
    FILTER_OPS,
    NUMBER,
    SCALE,
    QUESTION_PREFIX,
    RESPONDENT,
    SOURCE,
    SOURCE_GROUPS,
    SQL_ONLY_BUILTINS,
    STATUS,
    STATUS_GROUPS,
    SUBMITTED_AT,
    YES_NO,
    BUILTINS,
    ENDING,
    RESPONDENT_GROUPS,
    Catalogue,
    ReportField,
)

INVALID = "invalid_definition"
UNKNOWN_FIELD = "unknown_field"
NOT_REPORTABLE = "field_not_reportable"
OP_NOT_ALLOWED = "op_not_allowed"

BUCKETS = ("day", "week", "month", "year")
CARD_KINDS = ("tile", "bar", "donut", "line", "table")
# a donut is parts of a whole: at most this many groups, from a dimension that
# has a fixed, known set of them
DONUT_GROUPS_MAX = 6


def error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status, content={"code": code, "message": message, **extra})


def invalid(message: str) -> HTTPException:
    return error(HTTPStatus.UNPROCESSABLE_ENTITY, INVALID, message)


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, alias_generator=to_camel, frozen=True
    )


Scalar = Union[StrictBool, StrictInt, StrictFloat, StrictStr]


class Clause(_Model):
    """One condition on an answer: a question, an operator and a value that is
    an option id of that question, a number, a yes/no or a date, never text a
    respondent wrote (``value`` is checked against the question when the
    definition is validated)."""

    field: str = Field(min_length=1, max_length=100)
    op: Literal[ALL_OPS]  # type: ignore[valid-type]
    value: Optional[Union[Scalar, Tuple[Scalar, ...]]] = Field(
        default=None
    )

    @model_validator(mode="after")
    def _short(self):
        if isinstance(self.value, tuple) and len(self.value) > limits.CLAUSE_VALUES_MAX:
            raise ValueError("too many values")
        if isinstance(self.value, str) and len(self.value) > limits.CLAUSE_VALUE_MAX:
            raise ValueError("value too long")
        if isinstance(self.value, tuple) and any(
            isinstance(v, str) and len(v) > limits.CLAUSE_VALUE_MAX for v in self.value
        ):
            raise ValueError("value too long")
        return self


class Filters(_Model):
    """The filters of a report: the responses list's plaintext ones. No search
    (it is a respondent's address) and no filter on an answer."""

    submitted_from: Optional[AwareDatetime] = None
    submitted_to: Optional[AwareDatetime] = None
    status: Tuple[DeletionStatusFilter, ...] = Field(default=(), max_length=4)
    respondent: Optional[RespondentFilter] = None
    form_version: Tuple[int, ...] = Field(
        default=(), max_length=limits.FORM_VERSIONS_MAX
    )
    # conditions on answers, all of which a response meets (at most
    # ``limits.CLAUSES_MAX``); each is checked against the form's questions
    where: Tuple[Clause, ...] = Field(default=(), max_length=limits.CLAUSES_MAX)

    @model_validator(mode="after")
    def _ordered(self):
        if (
            self.submitted_from is not None
            and self.submitted_to is not None
            and self.submitted_to <= self.submitted_from
        ):
            raise ValueError("submittedTo must be after submittedFrom")
        if any(v < 0 or v > 1_000_000 for v in self.form_version):
            raise ValueError("formVersion out of range")
        return self

    def as_list_filters(self) -> ResponseListFilters:
        return ResponseListFilters(
            submitted_from=self.submitted_from,
            submitted_to=self.submitted_to,
            status=self.status,
            respondent=self.respondent,
            form_version=self.form_version,
        )


class Dimension(_Model):
    field: str = Field(min_length=1, max_length=100)
    bucket: Optional[Literal["day", "week", "month", "year"]] = None


class Measure(_Model):
    agg: Literal["count", "avg", "sum", "min", "max"]
    field: Optional[str] = Field(default=None, min_length=1, max_length=100)


class Card(_Model):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=limits.CARD_ID_MAX)
    kind: Literal["tile", "bar", "donut", "line", "table"]
    dimension: Optional[Dimension] = None
    measures: Tuple[Measure, ...] = Field(min_length=1, max_length=limits.MEASURES_MAX)
    title: Optional[str] = Field(default=None, max_length=limits.TITLE_MAX)


class Definition(_Model):
    v: Literal[1]
    filters: Filters = Filters()
    tz: str = Field(default="UTC", min_length=1, max_length=64)
    cards: Tuple[Card, ...] = Field(min_length=1, max_length=limits.CARDS_MAX)

    @model_validator(mode="after")
    def _unique_cards(self):
        ids = [card.id for card in self.cards]
        if len(set(ids)) != len(ids):
            raise ValueError("card ids must be unique")
        return self

    def canonical(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            sort_keys=True,
            separators=(",", ":"),
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical().encode()).hexdigest()[:32]


def parse(body: bytes) -> Definition:
    """The definition in a request body, or 422 ``invalid_definition``. The
    message names where it went wrong (a path and a rule), never a value."""
    if len(body) > limits.DEFINITION_MAX_BYTES:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            INVALID,
            f"A definition is at most {limits.DEFINITION_MAX_BYTES} bytes.",
        )
    try:
        return Definition.model_validate_json(body)
    except ValidationError as problem:
        first = problem.errors(include_url=False, include_context=False, include_input=False)[0]
        where = ".".join(str(part) for part in first["loc"]) or "definition"
        raise invalid(f"{where}: {first['msg']}") from None


# ------------------------------------------------------------------- the plan


@dataclass(frozen=True)
class DimensionPlan:
    """A card's dimension, resolved: a question (``field``) or a built-in."""

    key: str
    builtin: Optional[str] = None
    field: Optional[ReportField] = None
    bucket: Optional[str] = None

    @property
    def time(self) -> bool:
        return self.builtin == SUBMITTED_AT or (
            self.field is not None and self.field.kind == DATE
        )


@dataclass(frozen=True)
class MeasurePlan:
    agg: str
    field: Optional[ReportField] = None


@dataclass(frozen=True)
class ClausePlan:
    """A condition on an answer, resolved: the question, the operator and the
    operand in the form the matcher compares with (an option id or a set of
    them, a ``Decimal``, a ``date`` or a bool, a pair for ``between``)."""

    field: ReportField
    op: str
    operand: Any = None


@dataclass(frozen=True)
class CardPlan:
    id: str
    kind: str
    dimension: Optional[DimensionPlan]
    measures: Tuple[MeasurePlan, ...]

    @property
    def needs_answers(self) -> bool:
        """The card reads answers (a question as dimension or an aggregate of
        one); otherwise it is counted from plaintext columns in SQL."""
        return (
            self.dimension is not None and self.dimension.field is not None
        ) or any(m.field is not None for m in self.measures)


@dataclass(frozen=True)
class Plan:
    definition: Definition
    cards: Tuple[CardPlan, ...]
    tz: ZoneInfo
    filters: ResponseListFilters
    # conditions on answers: with any, every card is computed in the pass, because
    # which responses count depends on what they answered
    clauses: Tuple[ClausePlan, ...] = ()

    @property
    def scan_cards(self) -> Tuple[CardPlan, ...]:
        if self.clauses:
            return self.cards
        return tuple(c for c in self.cards if c.needs_answers)

    @property
    def sql_cards(self) -> Tuple[CardPlan, ...]:
        if self.clauses:
            return ()
        return tuple(c for c in self.cards if not c.needs_answers)

    @property
    def needs_answers(self) -> bool:
        return bool(self.clauses) or any(c.needs_answers for c in self.cards)

    def scan_digest(self) -> str:
        """What the cached aggregates are keyed by: the filters, the zone and
        the cards that read answers (not the cards counted in SQL)."""
        scan = [c.id for c in self.scan_cards]
        data = json.loads(self.definition.canonical())
        data["cards"] = [c for c in data["cards"] if c["id"] in scan]
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:32]

    @property
    def uses_deletion_status(self) -> bool:
        return bool(self.filters.status) or any(
            c.dimension is not None and c.dimension.builtin == STATUS
            for c in self.cards
        )


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise invalid("tz: not a time zone of the IANA database") from None


def _resolve(key: str, catalogue: Catalogue) -> Tuple[Optional[str], Optional[ReportField]]:
    """A field key as a built-in dimension or a question of the catalogue; the
    two refusals are the same for a question that does not exist and one the
    caller may not use."""
    if key in BUILTINS:
        return key, None
    found = catalogue.get(key) if key.startswith(QUESTION_PREFIX) else None
    if found is not None:
        return None, found
    if key.startswith(QUESTION_PREFIX) and key in catalogue.unreportable:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            NOT_REPORTABLE,
            "This question cannot be used in a report.",
        )
    raise error(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        UNKNOWN_FIELD,
        "No such question in this form.",
    )


def _dimension_plan(card: Card, catalogue: Catalogue) -> Optional[DimensionPlan]:
    dimension = card.dimension
    if dimension is None:
        return None
    builtin, found = _resolve(dimension.field, catalogue)
    if found is not None and not found.dimension:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            NOT_REPORTABLE,
            "This question cannot be used to group a report.",
        )
    timed = builtin == SUBMITTED_AT or (found is not None and found.kind == DATE)
    if dimension.bucket is not None and not timed:
        raise invalid("A bucket only applies to a date.")
    bucket = (dimension.bucket or "day") if timed else None
    return DimensionPlan(key=dimension.field, builtin=builtin, field=found, bucket=bucket)


def _measure_plan(measure: Measure, catalogue: Catalogue) -> MeasurePlan:
    if measure.agg == COUNT:
        if measure.field is not None:
            raise invalid("Count has no field; it counts responses.")
        return MeasurePlan(COUNT)
    if measure.field is None:
        raise invalid(f"{measure.agg} needs a field.")
    builtin, found = _resolve(measure.field, catalogue)
    if found is None:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            OP_NOT_ALLOWED,
            f"{measure.agg} cannot be taken of this field.",
        )
    if measure.agg not in found.measures:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            OP_NOT_ALLOWED,
            f"{measure.agg} cannot be taken of this question.",
        )
    return MeasurePlan(measure.agg, found)


def _fixed_groups(dimension: DimensionPlan, catalogue: Catalogue) -> Optional[int]:
    """How many groups a dimension has when that is known up front (None:
    not known)."""
    if dimension.field is not None:
        found = dimension.field
        if found.kind == CHOICE:
            return len(found.options) + 2  # the options, "Other", "Removed option"
        if found.kind == YES_NO:
            return 2
        return None
    return {
        RESPONDENT: len(RESPONDENT_GROUPS),
        SOURCE: len(SOURCE_GROUPS),
        STATUS: len(STATUS_GROUPS),
        ENDING: len(catalogue.endings) + 1,
    }.get(dimension.builtin or "")


def _check_kind(card: Card, dimension: Optional[DimensionPlan], catalogue: Catalogue) -> None:
    if card.kind == "tile" and dimension is not None:
        raise invalid("A tile has no dimension.")
    if card.kind in ("bar", "donut", "line") and dimension is None:
        raise invalid(f"A {card.kind} needs a dimension.")
    if card.kind == "line" and not (dimension and dimension.time):
        raise invalid("A line needs a time dimension.")
    if card.kind == "donut":
        groups = _fixed_groups(dimension, catalogue) if dimension else None
        if dimension is not None and dimension.field is not None and dimension.field.kind == "choices":
            raise invalid("A donut needs a dimension whose groups are parts of a whole.")
        if groups is None or groups > DONUT_GROUPS_MAX:
            raise invalid(f"A donut needs a dimension with at most {DONUT_GROUPS_MAX} groups.")


_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER_LIMIT = 10**15


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise invalid("where: a number is needed")
    if isinstance(value, float) and not math.isfinite(value):
        raise invalid("where: a number is needed")
    if abs(value) > _NUMBER_LIMIT:
        raise invalid("where: a number is out of range")
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def _day(value: Any) -> dt.date:
    if not isinstance(value, str) or not _DAY.match(value):
        raise invalid("where: a date as YYYY-MM-DD is needed")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise invalid("where: not a date") from None


def _pair(value: Any, convert) -> Tuple[Any, Any]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise invalid("where: between needs two values")
    low, high = convert(value[0]), convert(value[1])
    if low > high:
        raise invalid("where: the first value of between is after the second")
    return low, high


def _options(field_: ReportField, value: Any, many: bool) -> Any:
    known = {option_id for option_id, _ in field_.options}
    ids = value if isinstance(value, tuple) else (value,)
    if many and not isinstance(value, tuple):
        raise invalid("where: a list of options is needed")
    if not many and isinstance(value, tuple):
        raise invalid("where: one option is needed")
    if not ids or any(not isinstance(i, str) or i not in known for i in ids):
        # the same answer for an option that never existed and one that is gone
        raise invalid("where: no such option in this question")
    return frozenset(ids) if many else ids[0]


def clause_plan(clause: Clause, catalogue: Catalogue) -> ClausePlan:
    """A condition resolved against the catalogue the caller may use: a question
    that does not exist and one the caller may not use are refused alike, as is
    an operator the question's kind does not take; the value must suit the
    operator (an option of the question, a number, a yes/no, a date)."""
    if not clause.field.startswith(QUESTION_PREFIX):
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            NOT_REPORTABLE,
            "Only a question can be filtered on here; the list filters narrow by the rest.",
        )
    _, found = _resolve(clause.field, catalogue)
    assert found is not None
    if clause.op not in FILTER_OPS.get(found.kind, ()):
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            OP_NOT_ALLOWED,
            f"{clause.op} cannot be used on this question.",
        )
    op, value = clause.op, clause.value
    if op in ("is_empty", "is_not_empty"):
        if value is not None:
            raise invalid(f"where: {op} takes no value")
        return ClausePlan(found, op)
    if value is None:
        raise invalid(f"where: {op} needs a value")
    if found.kind == CHOICE:
        return ClausePlan(found, op, _options(found, value, many=op == "any_of"))
    if found.kind == CHOICES:
        return ClausePlan(found, op, _options(found, value, many=True))
    if op == "is":
        if not isinstance(value, bool):
            raise invalid("where: true or false is needed")
        return ClausePlan(found, op, value)
    if found.kind == DATE:
        if op == "between":
            return ClausePlan(found, op, _pair(value, _day))
        return ClausePlan(found, op, _day(value))
    if op == "between":
        return ClausePlan(found, op, _pair(value, _number))
    return ClausePlan(found, op, _number(value))


def validate(definition: Definition, catalogue: Catalogue) -> Plan:
    """The definition against the catalogue the caller may use, as a plan the
    engine runs; raises 422 with a code otherwise."""
    zone = _zone(definition.tz)
    cards: List[CardPlan] = []
    for card in definition.cards:
        dimension = _dimension_plan(card, catalogue)
        measures = tuple(_measure_plan(m, catalogue) for m in card.measures)
        if dimension is not None and dimension.builtin in SQL_ONLY_BUILTINS:
            if definition.filters.where:
                # counted in SQL, which never reads an answer: the condition would be ignored
                # for this card and its figures would not match the rest of the report
                raise error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    OP_NOT_ALLOWED,
                    "A condition on an answer cannot be combined with a card grouped by "
                    "deletion request or feedback status.",
                )
            if any(m.agg != COUNT for m in measures):
                raise error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    OP_NOT_ALLOWED,
                    "This dimension can only be combined with count.",
                )
        _check_kind(card, dimension, catalogue)
        cards.append(CardPlan(card.id, card.kind, dimension, measures))
    return Plan(
        definition=definition,
        cards=tuple(cards),
        tz=zone,
        filters=definition.filters.as_list_filters(),
        clauses=tuple(clause_plan(c, catalogue) for c in definition.filters.where),
    )
