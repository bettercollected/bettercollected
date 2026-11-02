"""One cell of the CSV file, read back as an answer: the exact inverse of
``response_export/table.py`` (docs/response-import.md has the table).

Nothing here decides whether an answer is acceptable: it only reads the text the
export writes (or a spreadsheet re-saved from it) into the shape the respondent
form posts. The respondent checks run afterwards on that shape
(``validation.py``). A cell that cannot be read raises ``CellProblem`` with a
code; the code never holds a value.
"""

import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from common.address import canonical_nl_postcode
from common.countries import DEFAULT_COUNTRY, is_country_code

from backend.app.services.response_export import table
from backend.app.services.response_import import limits

DRAWN_SIGNATURE_MARKER = "[drawn signature]"
_MAX_PIECES = 200
_NUMBER = re.compile(r"-?[0-9]{1,30}(?:[.,][0-9]{1,30})?")
_DATE_ISO = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")
_DATE_DMY = re.compile(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})")
_TIME = re.compile(r"([0-9]{1,2}):([0-9]{2})(?::[0-9]{2})?")
_CURRENCY = re.compile(r"([A-Za-z]{3})\s+(-?[0-9]{1,30}(?:[.,][0-9]{1,30})?)")
_NL_TOWN = re.compile(r"([0-9]{4}\s?[A-Za-z]{2})\s+(.+)")
_STREET = re.compile(
    r"(?P<street>.+?)\s+(?P<number>[0-9]{1,5})(?:\s+(?P<addition>[0-9A-Za-z][0-9A-Za-z /-]{0,9}))?"
)
_TRUE = {"yes", "y", "ja", "true", "1"}
_FALSE = {"no", "n", "nee", "false", "0"}


class CellProblem(Exception):
    """A cell that cannot be read as an answer to its question; ``code`` says why."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def clean(text: Any) -> str:
    """A cell as text: Unicode form C, the export's formula guard taken off
    (one leading ``'`` in front of what the export would have guarded: a
    formula character after any whitespace, or a tab or carriage return),
    surrounding space trimmed."""
    value = unicodedata.normalize("NFC", text if isinstance(text, str) else "")
    if value.startswith("'") and table.formula_like(value.lstrip("'")):
        value = value[1:]
    return value.strip()


def _answer(field_: Dict[str, Any], kind: str, **slots: Any) -> Dict[str, Any]:
    return {"field": {"id": str(field_.get("id"))}, "type": kind, **slots}


def parse_date(text: str) -> str:
    """``YYYY-MM-DD``; ``DD-MM-YYYY`` / ``DD/MM/YYYY`` / ``DD.MM.YYYY`` too (how a
    spreadsheet shows it again). ``CellProblem('invalid_date')`` otherwise or
    for a day that does not exist."""
    found = _DATE_ISO.fullmatch(text)
    if found:
        year, month, day = (int(p) for p in found.groups())
    else:
        found = _DATE_DMY.fullmatch(text)
        if not found:
            raise CellProblem("invalid_date")
        day, month, year = (int(p) for p in found.groups())
    try:
        return dt.date(year, month, day).isoformat()
    except ValueError:
        raise CellProblem("invalid_date") from None


def parse_time(text: str) -> str:
    found = _TIME.fullmatch(text)
    if not found:
        raise CellProblem("invalid_time")
    hour, minute = int(found.group(1)), int(found.group(2))
    if hour > 23 or minute > 59:
        raise CellProblem("invalid_time")
    return f"{hour:02d}:{minute:02d}"


def parse_number(text: str, decimal_comma: bool = False):
    """An integer when whole, else a float; a comma is a decimal point only
    when ``decimal_comma`` (a file separated by ``;``: a spreadsheet in Dutch
    writes ``12,5``); no thousands separators. In a file separated by commas
    a comma in a number is refused: ``1,234`` is not read as 1.234."""
    if not _NUMBER.fullmatch(text) or ("," in text and not decimal_comma):
        raise CellProblem("invalid_number")
    value = Decimal(text.replace(",", "."))
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _amount(text: str, decimal_comma: bool = False) -> str:
    if "," in text and not decimal_comma:
        raise CellProblem("invalid_amount")
    text = text.replace(",", ".")
    try:
        Decimal(text)
    except InvalidOperation:
        raise CellProblem("invalid_amount") from None
    return text


def _currency(field_: Dict[str, Any], text: str, decimal_comma: bool = False) -> Dict[str, Any]:
    found = _CURRENCY.fullmatch(text)
    if found:
        code, amount = found.group(1).upper(), _amount(found.group(2), decimal_comma)
    elif _NUMBER.fullmatch(text):
        allowed = [c for c in (_props(field_).get("currencies") or []) if isinstance(c, str)]
        if len(allowed) != 1:
            raise CellProblem("currency_missing")
        code, amount = allowed[0], _amount(text, decimal_comma)
    else:
        raise CellProblem("invalid_amount")
    return {"code": code, "amount": amount}


def _props(field_: Dict[str, Any]) -> Dict[str, Any]:
    props = field_.get("properties")
    return props if isinstance(props, dict) else {}


def _date_range(text: str) -> Dict[str, str]:
    start, slash, end = text.partition("/")
    if not slash or "/" in end:
        raise CellProblem("invalid_date_range")
    out: Dict[str, str] = {}
    try:
        if start.strip():
            out["start"] = parse_date(start.strip())
        if end.strip():
            out["end"] = parse_date(end.strip())
    except CellProblem:
        raise CellProblem("invalid_date_range") from None
    return out


def _tags(text: str) -> List[str]:
    pieces = [p.strip() for p in text.split(";")]
    if len(pieces) > _MAX_PIECES:
        raise CellProblem("too_many_choices")
    return [p for p in pieces if p]


def parse_address(text: str) -> Dict[str, str]:
    """The export's one line, ``street number addition, postcode city`` and the
    country code unless it is ``NL``, read back into parts. Best effort: a line
    that does not fit is ``unreadable_address``."""
    if len(text) > _MAX_ADDRESS_CHARS:
        raise CellProblem("unreadable_address")
    segments = [s.strip() for s in text.split(",") if s.strip()]
    country = DEFAULT_COUNTRY
    if len(segments) >= 2 and is_country_code(segments[-1].upper()) and len(segments[-1]) == 2:
        country = segments.pop().upper()
    if not segments or len(segments) > 2:
        raise CellProblem("unreadable_address")
    street_segment: Optional[str] = None
    town_segment: Optional[str] = None
    if len(segments) == 2:
        street_segment, town_segment = segments
    elif _NL_TOWN.match(segments[0]) or canonical_nl_postcode(segments[0]):
        town_segment = segments[0]
    else:
        street_segment = segments[0]
    parts: Dict[str, str] = {}
    if street_segment:
        found = _STREET.fullmatch(street_segment)
        if found:
            parts["street"] = found.group("street").strip()
            parts["house_number"] = found.group("number")
            if found.group("addition"):
                parts["house_number_addition"] = found.group("addition").strip()
        else:
            parts["street"] = street_segment
    if town_segment:
        found = _NL_TOWN.fullmatch(town_segment)
        if found:
            parts["postcode"] = canonical_nl_postcode(found.group(1)) or found.group(1)
            parts["city"] = found.group(2).strip()
        elif canonical_nl_postcode(town_segment):
            parts["postcode"] = canonical_nl_postcode(town_segment)
        else:
            first, _, rest = town_segment.partition(" ")
            if rest and any(ch.isdigit() for ch in first):
                parts["postcode"], parts["city"] = first, rest.strip()
            else:
                parts["city"] = town_segment
    parts["country"] = country
    return parts


def _choices_of(field_: Dict[str, Any]) -> List[Tuple[str, str]]:
    out = []
    for choice in _props(field_).get("choices") or []:
        if isinstance(choice, dict) and choice.get("id") is not None:
            out.append((str(choice["id"]), str(choice.get("value") or "")))
    return out


_MAX_SPAN = 10
_MAX_ADDRESS_CHARS = 400


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


class _Lookup:
    """The options of one question, normalised once: by label, by the export's
    ``Item N`` fallback for an option with no label, and by id."""

    def __init__(self, options: List[Tuple[str, str]]):
        self.by_label: Dict[str, str] = {}
        self.unlabelled: List[Optional[str]] = []
        self.by_id: Dict[str, str] = {}
        span = 1
        for option_id, label in options:
            wanted = _norm(label)
            if wanted:
                self.by_label.setdefault(wanted, option_id)
            self.unlabelled.append(None if wanted else option_id)
            self.by_id.setdefault(option_id.casefold(), option_id)
            span = max(span, label.count(";") + 1, option_id.count(";") + 1)
        # the most pieces of a ";"-separated cell one option can span
        self.span = min(span, _MAX_SPAN)

    def match(self, text: str) -> Optional[str]:
        """The id of the option a piece of text names: by its label (case and
        spacing ignored), by ``Item N`` for an option with no label, or by id."""
        wanted = _norm(text)
        if not wanted:
            return None
        found = self.by_label.get(wanted)
        if found is not None:
            return found
        number = re.fullmatch(r"item ([0-9]+)", wanted)
        if number and 1 <= int(number.group(1)) <= len(self.unlabelled):
            option_id = self.unlabelled[int(number.group(1)) - 1]
            if option_id is not None:
                return option_id
        return self.by_id.get(wanted)


def _choice(field_: Dict[str, Any], text: str) -> Dict[str, Any]:
    props = _props(field_)
    lookup = _Lookup(_choices_of(field_))
    allow_other = bool(props.get("allow_other_choice"))
    multiple = field_.get("type") == "multiple_choice" and bool(props.get("allow_multiple_selection"))
    if not multiple:
        found = lookup.match(text)
        if found is not None:
            return _answer(field_, "choice", choice={"value": found})
        if allow_other:
            return _answer(field_, "choice", choice={"other": text})
        raise CellProblem("unknown_option")
    pieces = text.split(";")
    if len(pieces) > _MAX_PIECES:
        raise CellProblem("too_many_choices")
    chosen: List[str] = []
    others: List[str] = []
    index = 0
    while index < len(pieces):
        matched = None
        span = min(lookup.span, len(pieces) - index)
        # the longest run of pieces that names an option (a label may hold ";"),
        # never longer than the most pieces an option can have
        while span >= 1:
            matched = lookup.match(";".join(pieces[index : index + span]))
            if matched is not None:
                break
            span -= 1
        if matched is not None:
            if matched not in chosen:
                chosen.append(matched)
            index += span
            continue
        piece = pieces[index].strip()
        if piece:
            others.append(piece)
        index += 1
    if others and not allow_other:
        raise CellProblem("unknown_option")
    value: Dict[str, Any] = {"values": chosen}
    if others:
        value["other"] = "; ".join(others)
    return _answer(field_, "choices", choices=value)


def convert_cell(
    field_: Dict[str, Any], raw: str, now_iso: str, decimal_comma: bool = False
) -> Optional[Dict[str, Any]]:
    """The answer a cell holds for ``field_`` (the question's definition), or
    None for an empty cell. ``now_iso``: the time a typed signature is stamped.
    Raises ``CellProblem``."""
    text = clean(raw)
    if not text:
        return None
    kind = field_.get("type")
    if kind in ("short_text", "long_text"):
        return _answer(field_, "text", text=text)
    if kind == "email":
        return _answer(field_, "email", email=text)
    if kind == "url":
        return _answer(field_, "url", url=text)
    if kind == "phone_number":
        return _answer(field_, "phone_number", phone_number=text)
    if kind in ("number", "rating", "linear_rating"):
        return _answer(field_, "number", number=parse_number(text, decimal_comma))
    if kind in ("date", "day"):
        return _answer(field_, "date", date=parse_date(text))
    if kind == "time":
        return _answer(field_, "time", time=parse_time(text))
    if kind == "currency":
        return _answer(field_, "currency", currency=_currency(field_, text, decimal_comma))
    if kind == "date_range":
        return _answer(field_, "date_range", date_range=_date_range(text))
    if kind == "tags":
        tags = _tags(text)
        return _answer(field_, "tags", tags=tags) if tags else None
    if kind == "address":
        return _answer(field_, "address", address=parse_address(text))
    if kind == "yes_no":
        lowered = text.casefold()
        if lowered in _TRUE:
            return _answer(field_, "boolean", boolean=True)
        if lowered in _FALSE:
            return _answer(field_, "boolean", boolean=False)
        raise CellProblem("invalid_yes_no")
    if kind in ("multiple_choice", "dropdown"):
        return _choice(field_, text)
    if kind == "signature":
        if text == DRAWN_SIGNATURE_MARKER:
            raise CellProblem("drawn_signature")
        return _answer(field_, "signature", signature={"method": "typed", "name": text, "signed_at": now_iso})
    raise CellProblem("type_unsupported")


_SUBMITTED_DMY = re.compile(r"([0-9]{1,2})[-/.]([0-9]{1,2})[-/.]([0-9]{4})(?:[ T]([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?)?")


def parse_submitted_at(raw: str, now: dt.datetime) -> Optional[dt.datetime]:
    """The submission time in a cell, as an aware UTC time: ISO 8601 (with ``Z``
    or an offset; none means UTC, as the export's header says), ``YYYY-MM-DD``
    with an optional time, or ``DD-MM-YYYY`` / ``DD/MM/YYYY`` with an optional
    time. ``None`` for an empty cell. ``CellProblem`` for a time that cannot be
    read, lies in the future (more than five minutes) or before
    ``OLDEST_SUBMISSION_YEAR``."""
    text = clean(raw)
    if not text:
        return None
    value: Optional[dt.datetime] = None
    found = _SUBMITTED_DMY.fullmatch(text)
    try:
        if found:
            day, month, year, hour, minute, second = found.groups()
            value = dt.datetime(
                int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0),
                tzinfo=dt.timezone.utc,
            )
        else:
            iso = text.replace(" ", "T", 1) if re.match(r"[0-9]{4}-[0-9]{2}-[0-9]{2} ", text) else text
            if iso.endswith(("Z", "z")):
                iso = iso[:-1] + "+00:00"
            parsed = dt.datetime.fromisoformat(iso)
            value = parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
            value = value.astimezone(dt.timezone.utc)
    except (ValueError, OverflowError):
        raise CellProblem("invalid_date") from None
    if value.year < limits.OLDEST_SUBMISSION_YEAR:
        raise CellProblem("invalid_date")
    if value > now + dt.timedelta(minutes=5):
        raise CellProblem("future_date")
    return value
