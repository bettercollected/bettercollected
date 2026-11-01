"""The rules of an address answer (common.address) and the country list
(common.countries, compared with docs/spec/countries-v1.json)."""

import json
from pathlib import Path

import pytest

from common import address
from common.countries import COUNTRIES_MAX, COUNTRY_CODES, DEFAULT_COUNTRY, is_country_code

SPEC = Path(__file__).resolve().parents[2] / "docs/spec/countries-v1.json"


def _parts(**kw):
    base = {
        "street": "Keizersgracht",
        "house_number": "12",
        "postcode": "1015 CS",
        "city": "Amsterdam",
        "country": "NL",
    }
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


# --- countries ----------------------------------------------------------------


def test_the_country_list_is_the_shared_file():
    shared = json.loads(SPEC.read_text())
    assert sorted(COUNTRY_CODES) == shared["codes"]
    assert shared["maxCountries"] == COUNTRIES_MAX == 30
    assert len(COUNTRY_CODES) == 249
    assert DEFAULT_COUNTRY == "NL"


@pytest.mark.parametrize("value", ["NL", "BE", "DE", "US", "AX"])
def test_codes(value):
    assert is_country_code(value)


@pytest.mark.parametrize("value", ["nl", "XX", "NLD", "N", "", None, 5, "N1", " NL", "NL "])
def test_not_codes(value):
    assert not is_country_code(value)


# --- postcodes and house numbers --------------------------------------------------


@pytest.mark.parametrize("value", ["1015 CS", "9999 ZZ", "1000 AA", "2513 AA"])
def test_a_dutch_postcode_in_its_stored_form(value):
    assert address.is_nl_postcode(value)


@pytest.mark.parametrize(
    "value", ["1015CS", "1015 cs", "0123 AB", "1015 SS", "1015 SA", "1015 SD", "1015  CS", " 1015 CS", "1015 CS ", "101 CS", "1015 C", "1015 CSS", "١٠١٥ CS", None, 1015]
)
def test_not_a_dutch_postcode(value):
    assert not address.is_nl_postcode(value)


@pytest.mark.parametrize(
    "typed, canonical",
    [("1015cs", "1015 CS"), ("1015 CS", "1015 CS"), (" 1015Cs ", "1015 CS"), ("2513aa", "2513 AA")],
)
def test_a_typed_postcode_is_made_canonical(typed, canonical):
    assert address.canonical_nl_postcode(typed) == canonical


@pytest.mark.parametrize("typed", ["1015 SS", "0123 AB", "1015", "abc", "1015  CS", "1015-CS", "", None, "1015CS\nx"])
def test_a_typed_postcode_that_is_not_one(typed):
    assert address.canonical_nl_postcode(typed) is None


@pytest.mark.parametrize("value, ok", [("1", True), ("12", True), ("99999", True), ("0", False), ("012", False), ("123456", False), ("12a", False), ("", False), (12, False), ("١٢", False)])
def test_a_dutch_house_number(value, ok):
    assert address.is_nl_house_number(value) is ok


@pytest.mark.parametrize("value, ok", [("A", True), ("bis", True), ("2", True), ("hoog-2", True), ("1 hoog", True), ("-2", False), (" A", False), ("A ", False), ("x" * 11, False), ("", False), ("a;b", False)])
def test_a_dutch_addition(value, ok):
    assert address.is_nl_addition(value) is ok


@pytest.mark.parametrize("value, ok", [("1000", True), ("SW1A 1AA", True), ("10115", True), ("1", False), ("-1000", False), ("1000-", False), ("1000  10", False), ("x" * 13, False), ("@@", False)])
def test_a_postcode_of_another_country(value, ok):
    assert address.is_other_postcode(value) is ok


def test_the_lookup_key_is_two_valid_values():
    assert address.lookup_key("1015cs", " 12 ") == "1015CS 12"
    assert address.lookup_key("1015 CS", "12") == "1015CS 12"
    for postcode, number in (("1015 SS", "12"), ("1015 CS", "0"), ("1015 CS", "12a"), ("", ""), (None, "1")):
        assert address.lookup_key(postcode, number) is None


# --- text rules --------------------------------------------------------------------


@pytest.mark.parametrize("value", ["Keizersgracht", "Rue de l'Église", "Straße", "Å", "O'Brien Street"])
def test_clean_text(value):
    assert address.is_clean_text(value, 100)


@pytest.mark.parametrize(
    "value", ["", " x", "x ", "x\n", "x​", "x‮", "x­", "﻿x", "x y", "é", "x" * 101, None, 5, "\ud800", "x\udc00y", "x\ue000", "x\u0378"]
)
def test_not_clean_text(value):
    assert not address.is_clean_text(value, 100)


def test_the_shape():
    assert address.is_shape({})
    assert address.is_shape(_parts())
    assert address.is_shape({"street": None})
    for bad in ("x", None, [], {"floor": "3"}, {"street": 12}, {"street": ["a"]}):
        assert not address.is_shape(bad)


def test_hard_problems_hold_for_any_answer():
    assert address.hard_problem(_parts()) is None
    assert address.hard_problem({"street": ""}) is None
    assert address.hard_problem("x") is None
    assert address.hard_problem(_parts(street="x​")) == "format"
    assert address.hard_problem(_parts(city=" Amsterdam")) == "format"
    assert address.hard_problem(_parts(street="x" * 101)) == "too_long"
    assert address.hard_problem(_parts(country="NLD")) == "too_long"
    assert address.hard_problem(_parts(postcode="1" * 13)) == "too_long"


# --- the rules ---------------------------------------------------------------------


def test_a_good_address_breaks_nothing():
    assert address.problems(_parts()) == []
    assert address.problems(_parts(house_number_addition="bis")) == []
    assert address.problems(_parts(country=None)) == []  # one country allowed: assumed


def test_nothing_is_said_about_an_address_that_is_not_there():
    assert address.problems({}) == []
    assert address.problems({"street": ""}) == []
    assert address.problems("x") == []
    assert address.problems(None) == []


def test_a_missing_part_is_required_once():
    assert address.problems(_parts(street=None, city=None, postcode=None)) == ["required"]
    assert address.problems(_parts(country=None), ["NL", "BE"]) == ["required"]


def test_the_country_must_be_one_the_question_allows():
    assert address.problems(_parts(country="DE", postcode="10115"), ["NL", "DE"]) == []
    assert address.problems(_parts(country="DE", postcode="10115")) == ["country"]
    assert address.problems(_parts(country="nl")) == ["format"]
    assert address.problems(_parts(country="ZZ")) == ["format"]


def test_each_country_writes_its_own_forms():
    assert address.problems(_parts(postcode="1015CS")) == ["format"]
    assert address.problems(_parts(country="BE", postcode="1000"), ["BE"]) == []
    assert address.problems(_parts(country="BE", postcode="x"), ["BE"]) == ["format"]
    # a Belgian house number may be text; a Dutch one may not
    assert address.problems(_parts(country="BE", postcode="1000", house_number="12B"), ["BE"]) == []
    assert address.problems(_parts(house_number="12B")) == ["format"]


def test_a_rule_is_reported_once_however_many_parts_break_it():
    got = address.problems(_parts(postcode="x", house_number="y", street=None))
    assert got == ["required", "format"]


def test_a_long_part_is_too_long_and_not_also_a_format_problem():
    assert address.problems(_parts(street="x" * 101)) == ["too_long"]
    assert address.problems(_parts(postcode="1" * 13)) == ["too_long"]


def test_a_country_alone_is_no_answer_for_the_rules():
    assert address.problems({"country": "NL"}) == []
    assert address.problems({"country": "NL", "street": ""}) == []
    assert address.problems({"country": "XX"}) == []
    assert address.problems({"country": "NL", "street": "x"}) != []


def test_a_part_that_cannot_be_written_as_utf8_is_refused():
    for bad in ("\ud800", "Keizers\udfffgracht"):
        assert address.hard_problem(_parts(street=bad)) == "format"
        with pytest.raises(UnicodeEncodeError):
            bad.encode()


def test_any_part_but_the_country():
    assert address.has_any_part(_parts())
    assert not address.has_any_part({"country": "NL"})
    assert not address.has_any_part({"street": ""})
    assert not address.has_any_part(None)
