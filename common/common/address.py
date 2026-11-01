"""What an ``address`` answer may hold.

An answer is ``{"type": "address", "address": {...}}`` with the parts
``street``, ``house_number``, ``house_number_addition``, ``postcode``, ``city``
and ``country`` (an ISO 3166-1 alpha-2 code, ``common.countries``). Every part
is text, stored the way it is shown: trimmed, in Unicode form C, without control
or format characters (zero-width and bidirectional marks), and within the caps
below. A Dutch address (``NL``) is held to the Dutch forms: a postcode written
``1234 AB`` (one space, upper case; the letters not ``SA``, ``SD`` or ``SS``)
and a house number of one to five digits.

Nothing here knows whether an address exists: a street and a city that a lookup
filled in are as unverified as ones typed. The shared answer-validation corpus
(``docs/spec/answer-validation.cases.json``) holds the cases; the webapp's twin of these
rules (``webapp/src/utils/address.ts``) comes with the webapp change and runs the same corpus.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional

from common.countries import is_country_code

# Caps of one part (characters); the country is a two-letter code.
STREET_MAX = 100
CITY_MAX = 100
HOUSE_NUMBER_MAX = 10
ADDITION_MAX = 10
POSTCODE_MAX = 12
POSTCODE_MIN = 2

PARTS = (
    "street",
    "house_number",
    "house_number_addition",
    "postcode",
    "city",
    "country",
)
PART_MAX = {
    "street": STREET_MAX,
    "house_number": HOUSE_NUMBER_MAX,
    "house_number_addition": ADDITION_MAX,
    "postcode": POSTCODE_MAX,
    "city": CITY_MAX,
    "country": 2,
}

# Control (Cc), format (Cf: zero-width and bidirectional marks, the byte order
# mark, the soft hyphen), line/paragraph separators (Zl, Zp), lone surrogates
# (Cs: they cannot be encoded as UTF-8, so a JSON write or an export would
# fail), private use (Co) and unassigned code points (Cn) never belong in an
# address: they reverse or hide text in a view and defeat a comparison.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cn", "Co", "Cs", "Zl", "Zp"})

NL = "NL"
# 1234 AB: the first digit is never 0; the letters are never SA, SD or SS.
_NL_POSTCODE = re.compile(r"^[1-9][0-9]{3} [A-Z]{2}$")
_NL_POSTCODE_LOOSE = re.compile(r"^([1-9][0-9]{3}) ?([A-Za-z]{2})$")
_NL_BAD_LETTERS = frozenset({"SA", "SD", "SS"})
_NL_HOUSE_NUMBER = re.compile(r"^[1-9][0-9]{0,4}$")
_NL_ADDITION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z /-]{0,9}$")
_OTHER_POSTCODE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z -]{0,10}[0-9A-Za-z]$")


def is_clean_text(value: Any, limit: int, minimum: int = 1) -> bool:
    """Is ``value`` well-formed text for an address part: trimmed, in Unicode
    form C, ``minimum`` to ``limit`` characters, nothing forbidden?"""
    return (
        isinstance(value, str)
        and minimum <= len(value) <= limit
        and value == value.strip()
        and value == unicodedata.normalize("NFC", value)
        and not any(unicodedata.category(c) in _FORBIDDEN_CATEGORIES for c in value)
    )


def is_nl_postcode(value: Any) -> bool:
    """Is ``value`` a Dutch postcode in its stored form (``1234 AB``)?"""
    return (
        isinstance(value, str)
        and _NL_POSTCODE.fullmatch(value) is not None
        and value[5:] not in _NL_BAD_LETTERS
    )


def canonical_nl_postcode(value: Any) -> Optional[str]:
    """A Dutch postcode as typed (``1234ab``, ``1234 AB``, surrounding space
    ignored) in its stored form, or None when it is not one."""
    if not isinstance(value, str):
        return None
    found = _NL_POSTCODE_LOOSE.fullmatch(value.strip())
    if found is None:
        return None
    canonical = f"{found.group(1)} {found.group(2).upper()}"
    return canonical if is_nl_postcode(canonical) else None


def is_nl_house_number(value: Any) -> bool:
    """Is ``value`` a Dutch house number: one to five digits, not starting
    with 0?"""
    return isinstance(value, str) and _NL_HOUSE_NUMBER.fullmatch(value) is not None


def is_nl_addition(value: Any) -> bool:
    """Is ``value`` a Dutch house number addition (a letter, a number or a
    short word, up to ``ADDITION_MAX`` characters)?"""
    return (
        isinstance(value, str)
        and _NL_ADDITION.fullmatch(value) is not None
        and not value.endswith(" ")
    )


def is_other_postcode(value: Any) -> bool:
    """Is ``value`` a postcode of another country: letters, digits, spaces and
    hyphens, two to ``POSTCODE_MAX`` characters, starting and ending with a
    letter or a digit? (The shapes differ too much to hold to one.)"""
    return (
        isinstance(value, str)
        and POSTCODE_MIN <= len(value) <= POSTCODE_MAX
        and _OTHER_POSTCODE.fullmatch(value) is not None
        and "  " not in value
    )


def lookup_key(postcode: Any, house_number: Any) -> Optional[str]:
    """The postcode (``1234AB``, no space) and the house number the address
    lookup takes, from the typed values, or None when either is not valid."""
    canonical = canonical_nl_postcode(postcode)
    number = house_number.strip() if isinstance(house_number, str) else None
    if canonical is None or number is None or not is_nl_house_number(number):
        return None
    return canonical.replace(" ", "") + " " + number


def has_any_part(value: Any) -> bool:
    """Is any part but the country given? (A country alone is no answer.)"""
    return isinstance(value, dict) and any(
        isinstance(value.get(part), str) and value.get(part) != ""
        for part in PARTS
        if part != "country"
    )


def one_line(value: Any) -> str:
    """The address as one line for a table, an export or a message:
    ``street number addition, postcode city`` and the country code when it is
    not ``NL``. A part that is missing is left out; not an address: ``""``.
    (The webapp's ``addressLine`` follows the same shape.)"""
    if not isinstance(value, dict):
        return ""

    def text(part: str) -> str:
        found = value.get(part)
        return found.strip() if isinstance(found, str) else ""

    street = " ".join(p for p in (text("street"), text("house_number"), text("house_number_addition")) if p)
    town = " ".join(p for p in (text("postcode"), text("city")) if p)
    country = text("country")
    parts: List[str] = [p for p in (street, town) if p]
    if country and country != NL and parts:
        parts.append(country)
    return ", ".join(parts)


def plain_parts(value: Any) -> Dict[str, str]:
    """The parts of an answer that are text, by name (others dropped)."""
    if not isinstance(value, dict):
        return {}
    return {part: value[part] for part in PARTS if isinstance(value.get(part), str)}


# Rule codes (the answer rules' ``required``, ``format``, ``too_long`` and the
# address question's own ``country``).
REQUIRED = "required"
FORMAT = "format"
TOO_LONG = "too_long"
COUNTRY_NOT_ALLOWED = "country"


def is_shape(value: Any) -> bool:
    """Is ``value`` an address answer's shape: an object whose keys are some
    of the six parts and whose values are text or null?"""
    return (
        isinstance(value, dict)
        and set(value) <= set(PARTS)
        and all(v is None or isinstance(v, str) for v in value.values())
    )


def hard_problem(value: Any) -> Optional[str]:
    """What no stored address may break whatever its question says: a part
    that is not clean text (untrimmed, not in Unicode form C, a control or
    format character) is ``format``, one over its cap ``too_long``. Parts left
    out or empty are fine. ``None`` for something that is not the shape (the
    type check says so)."""
    if not is_shape(value):
        return None
    problem: Optional[str] = None
    for part, limit in PART_MAX.items():
        text = value.get(part)
        if not text:
            continue
        if len(text) > limit:
            return TOO_LONG
        if not is_clean_text(text, limit):
            problem = FORMAT
    return problem


def problems(value: Any, allowed_countries: Optional[List[str]] = None) -> List[str]:
    """The rules an answered address breaks, without repeats, in this order of
    first appearance: ``required`` (street, house number, postcode, city or,
    when the question allows several countries, the country is missing),
    ``format`` (a part is not what its country writes, the country not a
    code), ``country`` (not one the question allows), ``too_long``. A single
    allowed country is assumed when none is given. Nothing for something that
    is not an address answer or has no part at all (a country alone counts as none:
    Required's to say)."""
    if not is_shape(value) or not has_any_part(value):
        return []
    allowed = list(allowed_countries or [NL])
    found: List[str] = []

    def add(code: str) -> None:
        if code not in found:
            found.append(code)

    text = {part: (value.get(part) or "") for part in PARTS}
    country = text["country"] or (allowed[0] if len(allowed) == 1 else "")
    for part in ("street", "house_number", "postcode", "city"):
        if not text[part]:
            add(REQUIRED)
    if not country:
        add(REQUIRED)
    if text["country"]:
        if not is_country_code(text["country"]):
            add(FORMAT)
        elif text["country"] not in allowed:
            add(COUNTRY_NOT_ALLOWED)
    for part, limit in PART_MAX.items():
        if len(text[part]) > limit:
            add(TOO_LONG)
    if country == NL:
        if text["postcode"] and len(text["postcode"]) <= POSTCODE_MAX and not is_nl_postcode(text["postcode"]):
            add(FORMAT)
        if text["house_number"] and len(text["house_number"]) <= HOUSE_NUMBER_MAX and not is_nl_house_number(text["house_number"]):
            add(FORMAT)
        if text["house_number_addition"] and len(text["house_number_addition"]) <= ADDITION_MAX and not is_nl_addition(text["house_number_addition"]):
            add(FORMAT)
    elif country:
        if text["postcode"] and len(text["postcode"]) <= POSTCODE_MAX and not is_other_postcode(text["postcode"]):
            add(FORMAT)
    for part in ("street", "house_number", "house_number_addition", "city"):
        if text[part] and len(text[part]) <= PART_MAX[part] and not is_clean_text(text[part], PART_MAX[part]):
            add(FORMAT)
    return found
