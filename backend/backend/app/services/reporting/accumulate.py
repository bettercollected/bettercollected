"""The accumulators: what one pass over the responses adds up for each card.

One ``CardAccumulator`` per card that reads answers. The engine feeds every
response to every accumulator, then drops the response: an accumulator holds
counts and exact sums per group, never an answer, an id or a respondent. A group
is keyed by an option id, a bucket, a number or a fixed word; the labels are
added at the end from the catalogue.

Semantics (docs/reporting.md):

* A response with no value for the card's dimension is *skipped* for that card
  and counted in ``skipped``; ``answered`` + ``skipped`` is every response the
  card saw.
* A multiple choice response is counted in each option it chose, so the groups
  of such a card add up to more than ``answered``.
* An answer is counted as stored: a question logic hid, or a jump skipped, still
  counts when an answer is stored (the responses export does the same). The
  cards say "answered", never "saw".
* Averages and sums are exact (``Decimal``); an average of no values is
  ``None``, never 0; the average is rounded to two decimals at the edge.
* A typed "Other" is one group, ``other``; its text is never read.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from backend.app.services.reporting import limits
from backend.app.services.reporting.catalogue import (
    AVG,
    CALCULATED,
    CHOICE,
    CHOICES,
    COUNT,
    CURRENCY,
    DATE,
    ENDING,
    FORM_VERSION,
    MAX,
    MIN,
    NONE_KEY,
    NUMBER,
    OTHER_KEY,
    OTHER_LABEL,
    REMOVED_KEY,
    REMOVED_LABEL,
    RESPONDENT,
    RESPONDENT_GROUPS,
    SCALE,
    SOURCE,
    SOURCE_GROUPS,
    STATUS,
    STATUS_GROUPS,
    SUBMITTED_AT,
    SUM,
    YES_NO,
    YES_NO_GROUPS,
    Catalogue,
    ReportField,
)
from backend.app.services.reporting.definition import CardPlan, DimensionPlan

TWO_PLACES = Decimal("0.01")
ALL_KEY = "all"


def bucket_key(day: dt.date, bucket: str) -> str:
    """The key of the bucket a day falls in: the day, the Monday of its week,
    ``YYYY-MM`` or ``YYYY``."""
    if bucket == "week":
        return (day - dt.timedelta(days=day.weekday())).isoformat()
    if bucket == "month":
        return f"{day.year:04d}-{day.month:02d}"
    if bucket == "year":
        return f"{day.year:04d}"
    return day.isoformat()


@dataclass
class ResponseView:
    """What the pass knows of one response: its plaintext columns and its
    decrypted answers (``None`` when they could not be read)."""

    created_at: Optional[dt.datetime]
    form_version: Optional[int]
    anonymous: bool
    ending_id: Optional[str]
    source: str
    answers: Optional[Dict[str, Any]]


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _decimal(value: Any) -> Optional[Decimal]:
    """A stored number as an exact decimal; booleans, NaN and infinities are
    no numbers."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            return Decimal(repr(value)) if math.isfinite(value) else None
        if isinstance(value, str):
            number = Decimal(value.strip())
            return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None
    return None


def numeric_value(field_: ReportField, answers: Dict[str, Any]) -> Optional[Decimal]:
    """The number a numeric question's answer holds, or None."""
    answer = _dict(answers.get(field_.id))
    if field_.kind == CURRENCY:
        currency = _dict(answer.get("currency"))
        if currency.get("code") not in (None, field_.currency):
            return None
        amount = currency.get("amount")
        return _decimal(amount) if isinstance(amount, str) else None
    if field_.kind in (SCALE, NUMBER, CALCULATED):
        number = answer.get("number")
        return None if isinstance(number, bool) else _decimal(number)
    return None


def _choice_keys(field_: ReportField, answer: Dict[str, Any]) -> List[str]:
    known = {option_id for option_id, _ in field_.options}
    if field_.kind == CHOICES:
        block = _dict(answer.get("choices"))
        picked = block.get("values")
        keys: List[str] = []
        removed = False
        for option_id in picked if isinstance(picked, list) else []:
            if not isinstance(option_id, str) or not option_id:
                continue
            if option_id in known:
                if option_id not in keys:
                    keys.append(option_id)
            else:
                removed = True
        if removed:
            keys.append(REMOVED_KEY)
        other = block.get("other")
        if isinstance(other, str) and other.strip():
            keys.append(OTHER_KEY)
        return keys
    block = _dict(answer.get("choice"))
    value = block.get("value")
    if isinstance(value, str) and value:
        if value in known:
            return [value]
        return [REMOVED_KEY]
    other = block.get("other")
    if isinstance(other, str) and other.strip():
        return [OTHER_KEY]
    return []


def _day_of(value: Any) -> Optional[dt.date]:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def question_keys(
    field_: ReportField, answers: Dict[str, Any], bucket: Optional[str]
) -> List[str]:
    """The groups one response falls in for a question as dimension (none:
    it gave no value)."""
    answer = _dict(answers.get(field_.id))
    if not answer:
        return []
    if field_.kind in (CHOICE, CHOICES):
        return _choice_keys(field_, answer)
    if field_.kind == YES_NO or field_.kind == CALCULATED:
        flag = answer.get("boolean")
        return [] if not isinstance(flag, bool) else ["yes" if flag else "no"]
    if field_.kind == SCALE:
        number = numeric_value(field_, answers)
        if number is None or number != number.to_integral_value():
            return []
        return [str(int(number))]
    if field_.kind == DATE:
        day = _day_of(answer.get("date"))
        return [] if day is None else [bucket_key(day, bucket or "day")]
    return []


def builtin_keys(
    builtin: str,
    view: ResponseView,
    bucket: Optional[str],
    tz: ZoneInfo,
    endings: frozenset = frozenset(),
) -> List[str]:
    if builtin == SUBMITTED_AT:
        if view.created_at is None:
            return []
        moment = view.created_at
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=dt.timezone.utc)
        return [bucket_key(moment.astimezone(tz).date(), bucket or "day")]
    if builtin == FORM_VERSION:
        return [str(view.form_version or 0)]
    if builtin == RESPONDENT:
        return ["anonymous" if view.anonymous else "known"]
    if builtin == ENDING:
        if not view.ending_id:
            return [NONE_KEY]
        # an ending no version of the form has any more
        return [view.ending_id if view.ending_id in endings else REMOVED_KEY]
    if builtin == SOURCE:
        return [view.source]
    return []


@dataclass
class _Group:
    n: int = 0
    # per measure: answered, exact sum, min, max
    answered: List[int] = field(default_factory=list)
    total: List[Decimal] = field(default_factory=list)
    low: List[Optional[Decimal]] = field(default_factory=list)
    high: List[Optional[Decimal]] = field(default_factory=list)


@dataclass
class GroupTotals:
    """A finished group: its key, how many responses it holds, and per measure
    the value (None: no answers) and how many answers it came from."""

    key: str
    n: int
    values: List[Optional[Any]]
    value_n: List[int]


@dataclass
class CardTotals:
    """What a card's accumulator ends with, before labels and ordering."""

    n: int
    answered: int
    skipped: int
    groups: Dict[str, GroupTotals]
    other_n: int = 0
    other_count: int = 0
    truncated: bool = False


def _plain(number: Decimal) -> Any:
    """A decimal as a JSON number: an int when it is whole."""
    if number == number.to_integral_value():
        return int(number)
    return float(number)


class CardAccumulator:
    def __init__(self, plan: CardPlan, tz: ZoneInfo, endings: frozenset = frozenset()):
        self.plan = plan
        self._tz = tz
        self._endings = endings
        self._groups: Dict[str, _Group] = {}
        self._n = 0
        self._answered = 0
        # no dimension: the answers of the first number measure say how many
        # of the responses the card is about
        self._first_numeric = next(
            (i for i, m in enumerate(plan.measures) if m.agg != COUNT), None
        )
        self._overflow_n = 0
        # the groups cut off (bounded: the count of them is then a floor)
        self._cut: set = set()
        self._truncated = False

    def _keys(self, view: ResponseView) -> List[str]:
        dimension: Optional[DimensionPlan] = self.plan.dimension
        if dimension is None:
            return [ALL_KEY]
        if dimension.builtin is not None:
            return builtin_keys(
                dimension.builtin, view, dimension.bucket, self._tz, self._endings
            )
        if view.answers is None or dimension.field is None:
            return []
        return question_keys(dimension.field, view.answers, dimension.bucket)

    def _group(self, key: str) -> Optional[_Group]:
        group = self._groups.get(key)
        if group is not None:
            return group
        if len(self._groups) >= limits.GROUPS_KEPT_MAX:
            self._truncated = True
            return None
        size = len(self.plan.measures)
        group = _Group(
            answered=[0] * size,
            total=[Decimal(0)] * size,
            low=[None] * size,
            high=[None] * size,
        )
        self._groups[key] = group
        return group

    def feed(self, view: ResponseView) -> None:
        self._n += 1
        keys = self._keys(view)
        if self.plan.dimension is not None and not keys:
            return
        numbers: List[Optional[Decimal]] = [None] * len(self.plan.measures)
        for index, measure in enumerate(self.plan.measures):
            if measure.agg != COUNT and measure.field is not None and view.answers is not None:
                numbers[index] = numeric_value(measure.field, view.answers)
        if self.plan.dimension is None:
            if self._first_numeric is None or numbers[self._first_numeric] is not None:
                self._answered += 1
        else:
            self._answered += 1
        for key in dict.fromkeys(keys):
            group = self._group(key)
            if group is None:
                self._overflow_n += 1
                if len(self._cut) < limits.GROUPS_CUT_TRACKED_MAX:
                    self._cut.add(key)
                continue
            group.n += 1
            for index, number in enumerate(numbers):
                if number is None:
                    continue
                group.answered[index] += 1
                group.total[index] += number
                if group.low[index] is None or number < group.low[index]:
                    group.low[index] = number
                if group.high[index] is None or number > group.high[index]:
                    group.high[index] = number

    def finish(self) -> CardTotals:
        groups: Dict[str, GroupTotals] = {}
        for key, group in self._groups.items():
            values: List[Optional[Any]] = []
            counts: List[int] = []
            for index, measure in enumerate(self.plan.measures):
                if measure.agg == COUNT:
                    values.append(group.n)
                    counts.append(group.n)
                    continue
                counts.append(group.answered[index])
                if group.answered[index] == 0:
                    values.append(None)
                elif measure.agg == AVG:
                    average = group.total[index] / group.answered[index]
                    values.append(_plain(average.quantize(TWO_PLACES, ROUND_HALF_UP)))
                elif measure.agg == SUM:
                    values.append(_plain(group.total[index]))
                elif measure.agg == MIN:
                    values.append(_plain(group.low[index]))
                elif measure.agg == MAX:
                    values.append(_plain(group.high[index]))
                else:
                    values.append(None)
            groups[key] = GroupTotals(key, group.n, values, counts)
        return CardTotals(
            n=self._n,
            answered=self._answered,
            skipped=self._n - self._answered,
            groups=groups,
            other_n=self._overflow_n,
            other_count=len(self._cut),
            truncated=self._truncated,
        )


def feed_all(accumulators: Sequence[CardAccumulator], view: ResponseView) -> None:
    for accumulator in accumulators:
        accumulator.feed(view)


def labels_for(
    dimension: Optional[DimensionPlan], catalogue: Catalogue
) -> Dict[str, str]:
    """The label of each group key that has one beyond its own text."""
    if dimension is None:
        return {ALL_KEY: ""}
    labels: Dict[str, str] = {}
    if dimension.field is not None:
        found = dimension.field
        if found.kind in (CHOICE, CHOICES):
            labels.update(found.option_labels)
            labels[OTHER_KEY] = OTHER_LABEL
            labels[REMOVED_KEY] = REMOVED_LABEL
        elif found.kind in (YES_NO, CALCULATED):
            labels.update(dict(YES_NO_GROUPS))
        return labels
    if dimension.builtin == RESPONDENT:
        labels.update(dict(RESPONDENT_GROUPS))
    elif dimension.builtin == SOURCE:
        labels.update(dict(SOURCE_GROUPS))
    elif dimension.builtin == STATUS:
        labels.update(dict(STATUS_GROUPS))
    elif dimension.builtin == ENDING:
        labels.update(dict(catalogue.endings))
        labels[NONE_KEY] = "No ending"
        labels[REMOVED_KEY] = "Removed ending"
    return labels
