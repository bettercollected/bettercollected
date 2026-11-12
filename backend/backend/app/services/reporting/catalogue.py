"""What a report may use: the form's questions that are reportable, and the
built-in (plaintext) dimensions.

The catalogue is built from the form's published versions, oldest first, and
then its current draft, so a question that exists in several versions is one
entry (by question id) and a question that only older versions have still
works for the responses filled under them. Option labels are merged the same
way: the newest version that has an option names it, so a renamed option is one
group, and an option that only an older version has keeps that version's label.
An answer naming an option no version has any more is counted as "Removed
option" (never by id).

Only these kinds are reportable, decided by the type of the question and nothing
else:

========== ===================================== ================ ==================
kind       questions                             as dimension      measures
========== ===================================== ================ ==================
choice     dropdown, multiple choice (one)       yes              count
choices    multiple choice, dropdown (several)   yes              count
yes_no     yes/no                                yes              count
scale      rating, linear rating, opinion scale  yes              count avg min max
number     number                                no               count avg sum min max
currency   currency (one currency)               no               count avg sum min max
calculated calculated yes/no or number           yes (yes/no)     count avg sum min max
date       date, day                             yes (bucketed)   count
========== ===================================== ================ ==================

Never reportable, whatever else is true of the question: text, email, phone,
link, address, signature, file, matrix, table, ranking, tags, time, date range,
a repeating group and its children, a question whose options come from a source
(the labels would be another form's answers), an internal (staff-only) question,
and a typed "Other" (it is one group, "Other", and its text is never read).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from common.currencies import DEFAULT_CURRENCY

from backend.app.services.response_export.table import field_title

QUESTION_PREFIX = "q:"

# kinds
CHOICE = "choice"
CHOICES = "choices"
YES_NO = "yes_no"
SCALE = "scale"
NUMBER = "number"
CURRENCY = "currency"
CALCULATED = "calculated"
DATE = "date"

# aggregates
COUNT = "count"
AVG = "avg"
SUM = "sum"
MIN = "min"
MAX = "max"
AGGREGATES = (COUNT, AVG, SUM, MIN, MAX)
NUMERIC_KINDS = (SCALE, NUMBER, CURRENCY, CALCULATED)

# built-in dimensions (plaintext columns of the response row)
SUBMITTED_AT = "submitted_at"
FORM_VERSION = "form_version"
RESPONDENT = "respondent"
ENDING = "ending"
STATUS = "status"
FEEDBACK_STATUS = "feedback_status"
SOURCE = "source"
BUILTINS = (
    SUBMITTED_AT,
    FORM_VERSION,
    RESPONDENT,
    ENDING,
    STATUS,
    FEEDBACK_STATUS,
    SOURCE,
)
# built-ins that live in another table or in a part of the row that a change
# does not move (a deletion request, a feedback entry): counted in SQL only,
# so a cached aggregate can never be stale on their account
SQL_ONLY_BUILTINS = (STATUS, FEEDBACK_STATUS)

# the fixed groups of the built-ins that have them (key, label as an English
# default; the webapp translates the keys)
RESPONDENT_GROUPS = (("anonymous", "Anonymous"), ("known", "Identified"))
SOURCE_GROUPS = (("form", "Form"), ("api", "API"), ("csv", "CSV import"))
STATUS_GROUPS = (
    ("none", "No request"),
    ("pending", "Pending"),
    ("declined", "Declined"),
    ("success", "Done"),
)
OTHER_KEY = "other"
REMOVED_KEY = "removed"
NONE_KEY = "none"
OTHER_LABEL = "Other"
REMOVED_LABEL = "Removed option"
YES_NO_GROUPS = (("yes", "Yes"), ("no", "No"))

_CHOICE_TYPES = ("multiple_choice", "dropdown")
_SCALE_TYPES = ("rating", "linear_rating", "opinion_scale")
_DATE_TYPES = ("date", "day")


@dataclass(frozen=True)
class ReportField:
    """One reportable question."""

    key: str
    id: str
    label: str
    kind: str
    dimension: bool
    measures: Tuple[str, ...]
    # (option id, label) in the order the form lists them
    options: Tuple[Tuple[str, str], ...] = ()
    # the published versions that have the question, and whether the current
    # draft does
    versions: Tuple[int, ...] = ()
    in_current: bool = True
    # a currency question: the only currency its amounts are summed in
    currency: Optional[str] = None

    @property
    def option_labels(self) -> Dict[str, str]:
        return dict(self.options)

    def as_json(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "dimension": self.dimension,
            "measures": list(self.measures),
            "versions": list(self.versions),
            "inCurrentVersion": self.in_current,
        }
        if self.kind in (CHOICE, CHOICES):
            entry["options"] = [{"id": i, "label": l} for i, l in self.options]
        if self.kind == CURRENCY:
            entry["currency"] = self.currency
        return entry


@dataclass(frozen=True)
class Catalogue:
    """The reportable questions of a form (``fields``, in form order), and its
    endings (the labels of the ``ending`` built-in dimension)."""

    fields: Tuple[ReportField, ...] = ()
    endings: Tuple[Tuple[str, str], ...] = ()
    # keys of the questions that exist but are not reportable by their type
    # (text, address, a typed "Other" question, ...): refused with their own code
    unreportable: frozenset = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_key", {f.key: f for f in self.fields})

    def get(self, key: str) -> Optional[ReportField]:
        return self._by_key.get(key)  # type: ignore[attr-defined]

    def keys(self) -> frozenset:
        """Every question key the form has, reportable or not (what the field
        policy is asked about)."""
        return frozenset(self._by_key) | self.unreportable  # type: ignore[attr-defined]

    def restricted_to(self, visible: Iterable[str]) -> "Catalogue":
        """The catalogue as one caller may use it: only the questions whose key
        is in ``visible`` (``policy.ReportFieldPolicy``). The built-in
        dimensions are plaintext columns of the response row and always remain."""
        allowed = set(visible)
        return Catalogue(
            tuple(f for f in self.fields if f.key in allowed),
            self.endings,
            frozenset(k for k in self.unreportable if k in allowed),
        )

    def as_json(self) -> Dict[str, Any]:
        return {
            "fields": [f.as_json() for f in self.fields],
            "builtins": builtin_catalogue(self),
        }


def builtin_catalogue(catalogue: Optional[Catalogue] = None) -> List[Dict[str, Any]]:
    """The built-in dimensions, as the page lists them."""
    endings = catalogue.endings if catalogue else ()
    entries = [
        {"key": SUBMITTED_AT, "buckets": ["day", "week", "month", "year"]},
        {"key": FORM_VERSION},
        {"key": RESPONDENT, "groups": _groups(RESPONDENT_GROUPS)},
        {"key": ENDING, "groups": _groups(endings)},
        {"key": STATUS, "groups": _groups(STATUS_GROUPS), "measures": [COUNT]},
        {"key": FEEDBACK_STATUS, "measures": [COUNT]},
        {"key": SOURCE, "groups": _groups(SOURCE_GROUPS)},
    ]
    return entries


def _groups(pairs: Iterable[Tuple[str, str]]) -> List[Dict[str, str]]:
    return [{"key": key, "label": label} for key, label in pairs]


# ---------------------------------------------------------------- small helpers


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _get(mapping: Any, snake: str, camel: str) -> Any:
    mapping = _dict(mapping)
    return mapping[snake] if snake in mapping else mapping.get(camel)


def _type(field_: Dict[str, Any]) -> Optional[str]:
    kind = field_.get("type")
    return getattr(kind, "value", kind)


def _page_questions(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The questions on the pages of a page-based form, in page order (nothing
    for a form of any other builder: it has no reportable question)."""
    pages = [p for p in _list(form.get("fields")) if isinstance(p, dict)]
    if not pages or any(_type(page) != "slide" for page in pages):
        return []
    return [
        question
        for page in pages
        for question in _list(_dict(page.get("properties")).get("fields"))
        if isinstance(question, dict)
    ]


def _option_pairs(properties: Dict[str, Any]) -> Tuple[Tuple[str, str], ...]:
    pairs: List[Tuple[str, str]] = []
    seen = set()
    for choice in _list(properties.get("choices")):
        choice = _dict(choice)
        option_id = choice.get("id")
        if not isinstance(option_id, str) or not option_id or option_id in seen:
            continue
        seen.add(option_id)
        label = choice.get("label") or choice.get("value")
        pairs.append((option_id, label if isinstance(label, str) and label else option_id))
    return tuple(pairs)


def reportable(question: Dict[str, Any]) -> Optional[ReportField]:
    """The question as a report field, or None when its type is not reportable
    (see the module doc). Pure: a question dict in, a field out."""
    if question.get("internal"):
        return None
    question_id = question.get("id")
    if not isinstance(question_id, str) or not question_id:
        return None
    kind = _type(question)
    properties = _dict(question.get("properties"))
    label = field_title(question)
    key = QUESTION_PREFIX + question_id

    def make(kind_: str, dimension: bool, measures: Sequence[str], **extra) -> ReportField:
        return ReportField(
            key=key,
            id=question_id,
            label=label,
            kind=kind_,
            dimension=dimension,
            measures=tuple(measures),
            **extra,
        )

    if kind in _CHOICE_TYPES:
        if _get(properties, "option_source", "optionSource") is not None:
            return None
        options = _option_pairs(properties)
        if not options:
            return None
        multiple = bool(
            _get(properties, "allow_multiple_selection", "allowMultipleSelection")
        )
        return make(CHOICES if multiple else CHOICE, True, (COUNT,), options=options)
    if kind == "yes_no":
        return make(YES_NO, True, (COUNT,))
    if kind in _SCALE_TYPES:
        return make(SCALE, True, (COUNT, AVG, MIN, MAX))
    if kind == "number":
        return make(NUMBER, False, (COUNT, AVG, SUM, MIN, MAX))
    if kind == "currency":
        currencies = [c for c in _list(properties.get("currencies")) if isinstance(c, str)]
        # amounts in different currencies cannot be added or averaged
        if len(currencies) > 1:
            return None
        return make(
            CURRENCY,
            False,
            (COUNT, AVG, SUM, MIN, MAX),
            currency=currencies[0] if currencies else DEFAULT_CURRENCY,
        )
    if kind == "calculated":
        style = _dict(properties.get("format")).get("style")
        if style == "text":
            return None
        return make(CALCULATED, True, (COUNT, AVG, SUM, MIN, MAX))
    if kind in _DATE_TYPES:
        return make(DATE, True, (COUNT,))
    return None


# what a page holds that is not a question
_NOT_QUESTIONS = (None, "text", "statement", "page_break", "IMAGE_CONTENT", "VIDEO_CONTENT")


def _answerable(question: Dict[str, Any]) -> bool:
    """Is it a question (something a respondent answers), whatever its type?"""
    return (
        isinstance(question.get("id"), str)
        and bool(question["id"])
        and _type(question) not in _NOT_QUESTIONS
    )


def _endings(form: Dict[str, Any]) -> List[Tuple[str, str]]:
    found: List[Tuple[str, str]] = []
    for index, ending in enumerate(_list(form.get("thankyou_page") or form.get("thankyouPage"))):
        ending = _dict(ending)
        ending_id = ending.get("id") or f"ending-{index + 1}"
        label = ending.get("name") or ending.get("title") or ending_id
        found.append((str(ending_id), str(label)))
    return found


def build_catalogue(
    published: Sequence[Tuple[int, Dict[str, Any]]], current: Optional[Dict[str, Any]]
) -> Catalogue:
    """The catalogue of a form from its published versions as ``(version
    number, form dict)`` and its current draft (either may be missing)."""
    sources: List[Tuple[Optional[int], Dict[str, Any]]] = sorted(
        ((v, f) for v, f in published), key=lambda item: item[0]
    )
    if current is not None:
        sources.append((None, current))
    merged: Dict[str, ReportField] = {}
    order: List[str] = []
    versions: Dict[str, List[int]] = {}
    endings: Dict[str, str] = {}
    last_keys: set = set()
    unreportable: set = set()
    for number, form in sources:
        for ending_id, label in _endings(form):
            endings[ending_id] = label
        last_keys = set()
        for question in _page_questions(form):
            found = reportable(question)
            if found is None:
                if _answerable(question):
                    key = QUESTION_PREFIX + str(question["id"])
                    unreportable.add(key)
                    # a version that makes a question internal (or of a kind a
                    # report does not use) takes it back: its older entry goes
                    if merged.pop(key, None) is not None:
                        order.remove(key)
                continue
            last_keys.add(found.key)
            previous = merged.get(found.key)
            options = found.options
            if previous is not None and previous.options:
                # the newest version names an option and orders the list; an
                # option only older versions have follows, under its old label
                known = {option_id for option_id, _ in options}
                options = options + tuple(
                    (i, l) for i, l in previous.options if i not in known
                )
            if found.key not in merged:
                order.append(found.key)
            merged[found.key] = replace(found, options=options)
            if number is not None:
                versions.setdefault(found.key, []).append(number)
    # "current" is the draft, or the newest published version when there is none
    fields = tuple(
        replace(
            merged[key],
            versions=tuple(versions.get(key, ())),
            in_current=key in last_keys,
        )
        for key in order
    )
    return Catalogue(
        fields,
        tuple(endings.items()),
        frozenset(k for k in unreportable if k not in merged),
    )
