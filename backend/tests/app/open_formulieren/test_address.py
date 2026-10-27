"""``addressNL``: one component, five text questions. The address lookup that
fills street and place from postcode and house number is not carried; the
five parts are typed. The fixtures' own address components are covered by the
golden files (test_importer.py, test_importer_3x.py)."""

import pytest

from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.importer import archive_language, build_draft
from backend.app.services.open_formulieren.mapping import HOUSE_NUMBER_PATTERN, POSTCODE_PATTERN
from tests.app.open_formulieren.conftest import (
    archive_with,
    comp,
    describe,
    eq,
    hide,
    no_deadline,  # noqa: F401  (fixture)
    rule,
)

DUTCH = {
    "name": "Voorbeeld",
    "translations": {"nl": {"name": "Voorbeeld"}, "en": {"name": "Example"}},
}


def address(key="address", label="Home", **extra):
    return comp("addressNL", key, label, **{"deriveAddress": False, **extra})


def run(steps, version="4.0.6", **kw):
    return build_draft(read_archive(archive_with(steps, version=version, **kw)))


def questions(built):
    return [q for page in describe(built)["pages"] for q in page["questions"]]


def items(built, **match):
    return [i for i in built.report.items if all(i.get(k) == v for k, v in match.items())]


def rules_of(question):
    return question.get("validations", {})


@pytest.fixture(params=["4.0.6", "3.5.14"])
def version(request):
    return request.param


def test_an_address_becomes_five_text_questions_in_its_place(version):
    built = run([[comp("textfield", "before"), address(), comp("textfield", "after")]], version)
    got = questions(built)
    assert [q["title"] for q in got] == [
        "before",
        "Home – Street",
        "Home – House number",
        "Home – Addition",
        "Home – Postcode",
        "Home – Place",
        "after",
    ]
    assert {q["type"] for q in got} == {"short_text"}
    assert built.summary["fields"] == 7


def test_the_labels_follow_the_language_of_the_form(version):
    built = run([[address(label="Adres")]], version, form=DUTCH)
    assert [q["title"] for q in questions(built)] == [
        "Adres – Straat",
        "Adres – Huisnummer",
        "Adres – Toevoeging",
        "Adres – Postcode",
        "Adres – Plaats",
    ]


def test_the_component_s_own_translation_decides_over_the_form():
    translated = address(
        label="Address",
        openForms={"translations": {"nl": {"label": "Woonadres"}, "en": {"label": "Address"}}},
    )
    other = address("other", "Adres")
    built = run([[translated, other]], form=DUTCH)
    titles = [q["title"] for q in questions(built)]
    assert titles[0] == "Address – Street"  # its label is the English text
    assert titles[5] == "Adres – Straat"  # no translation of its own: the form's language
    assert archive_language(read_archive(archive_with([[]], form=DUTCH))) == "nl"
    assert archive_language(read_archive(archive_with([[]]))) == "en"


@pytest.mark.parametrize("name", ["all-components", "special-components"])
def test_the_language_of_a_real_export_is_read_from_its_names(name):
    from tests.app.open_formulieren.conftest import fixture_bytes

    assert archive_language(read_archive(fixture_bytes(f"{name}.en.zip"))) == "en"
    assert archive_language(read_archive(fixture_bytes("3.5.14/all-components.nl.zip"))) == "nl"
    assert archive_language(read_archive(fixture_bytes("all-components.nl.zip"))) == "nl"


def test_a_label_missing_falls_back_to_the_word_for_address():
    got = questions(run([[comp("addressNL", "a", "", deriveAddress=False)]]))
    assert got[0]["title"] == "Address – Street"
    got = questions(run([[comp("addressNL", "a", "", deriveAddress=False)]], form=DUTCH))
    assert got[0]["title"] == "Adres – Straat"


def test_required_applies_to_four_parts_and_the_addition_stays_optional():
    required = {"validate": {"required": True}, "deriveAddress": True}
    got = questions(run([[comp("addressNL", "a", "Home", **required)]]))
    assert [q["validations"]["required"] for q in got] == [True, True, False, True, True]
    got = questions(run([[address()]]))
    assert [q["validations"]["required"] for q in got] == [False] * 5


def test_street_and_place_are_not_required_when_the_source_never_asked_for_them():
    """Without the lookup the source shows only postcode, house number, letter
    and addition: street and place are filled from the register."""
    got = questions(run([[address(validate={"required": True})]]))
    assert [q["validations"]["required"] for q in got] == [False, True, False, True, False]


def test_the_answers_are_checked_like_the_source_checks_them():
    got = questions(run([[address()]]))
    assert rules_of(got[1])["regex"] == HOUSE_NUMBER_PATTERN
    assert rules_of(got[3])["regex"] == POSTCODE_PATTERN
    assert "regex" not in rules_of(got[0]) and "regex" not in rules_of(got[4])
    addition = rules_of(got[2])
    assert addition["max_length"] == 10
    import re

    for good in ("a", "bis", "2", "a2", "a 2", "a-2", "1hg"):
        assert re.fullmatch(addition["regex"], good), good
    for bad in ("a b c", "abcde", "a--2", " ", "a_2"):
        assert not re.fullmatch(addition["regex"], bad), bad
    for good in ("1", "12345"):
        assert re.fullmatch(rules_of(got[1])["regex"], good)
    for bad in ("123456", "1a", "٣"):
        assert not re.fullmatch(rules_of(got[1])["regex"], bad)


def test_the_components_own_postcode_and_place_patterns_are_carried_when_they_run():
    custom = address(
        openForms={
            "translations": {},
            "components": {
                "postcode": {"validate": {"pattern": "^1234 [A-Z]{2}$"}},
                "city": {"validate": {"pattern": "^Amsterdam$"}},
            },
        }
    )
    got = questions(run([[custom]]))
    assert rules_of(got[3])["regex"] == "^1234 [A-Z]{2}$"
    assert rules_of(got[4])["regex"] == "^Amsterdam$"


def test_a_pattern_that_does_not_run_is_reported_and_the_default_is_used():
    broken = address(
        openForms={
            "translations": {},
            "components": {
                "postcode": {"validate": {"pattern": "(unclosed"}},
                "city": {"validate": {"pattern": "(a+)+$" + "x" * 600}},
            },
        }
    )
    built = run([[broken]])
    got = questions(built)
    assert rules_of(got[3])["regex"] == POSTCODE_PATTERN
    assert "regex" not in rules_of(got[4])
    assert [i["detail"] for i in items(built, reason="validation_not_carried")] == [{"property": "pattern"}] * 2


def test_it_is_reported_once_as_converted_to_text_and_says_the_lookup_is_not_carried(version):
    built = run([[address(deriveAddress=True)]], version)
    (item,) = items(built, reason="converted_to_text")
    assert (item["code"], item["kind"], item["key"], item["label"]) == ("changed", "component", "address", "Home")
    assert item["detail"] == {"componentType": "addressNL", "questions": 5, "lookup": "not_carried"}
    assert item["severity"] == "warning"  # the lookup was on
    assert items(run([[address()]], version), reason="converted_to_text")[0]["severity"] == "info"
    assert items(built, reason="unsupported_component_type") == []
    assert built.summary["dropped"] == 0


def test_help_text_goes_with_the_first_question_and_the_width_with_all():
    got = questions(run([[address(description="Where you live", tooltip="Where you live", colSpan=6)]]))
    assert got[0]["description"] == "Where you live"
    assert all("description" not in q for q in got[1:])
    built = run([[comp("columns", "c", columns=[{"size": 6, "components": [address()]}, {"size": 6, "components": []}])]])
    assert [q["colSpan"] for q in questions(built)] == [6] * 5


def test_what_cannot_be_carried_of_the_component_is_reported():
    built = run(
        [
            [
                address(
                    prefill={"plugin": "demo", "attribute": "address"},
                    disabled=True,
                    validate={"plugins": ["some-plugin"]},
                    customConditional="return true;",
                )
            ]
        ]
    )
    got = {i["reason"] for i in items(built, key="address")}
    assert {"prefill_not_carried", "disabled_not_carried", "validation_not_carried", "custom_script_dropped", "converted_to_text"} <= got


def test_a_hidden_address_is_dropped_like_any_hidden_component():
    built = run([[address(hidden=True), comp("textfield", "keep")]])
    assert [q["title"] for q in questions(built)] == ["keep"]
    assert items(built, key="address")[0]["reason"] == "always_hidden"


# ------------------------------------------------------------ the keys


def test_two_addresses_with_the_same_key_keep_their_own_questions():
    built = run([[address("a", "One"), address("a", "Two")]])
    assert [q["title"] for q in questions(built)][::5] == ["One – Street", "Two – Street"]
    assert len(questions(built)) == 10
    assert len(items(built, reason="converted_to_text")) == 2


def test_the_questions_never_take_the_key_of_another_component():
    """A component keyed like one of the address's parts, before or after it,
    keeps its own key: a condition on it reaches it, not an address question."""
    other = comp("textfield", "address_streetName", "Other")
    clash = comp("textfield", "address.streetName", "Dotted")
    built = run(
        [
            [
                other,
                address(),
                clash,
                comp("textfield", "later", conditional={"show": True, "when": "address_streetName", "eq": "x"}),
            ]
        ]
    )
    got = questions(built)
    assert got[-1]["logic"]["conditions"][0]["source"] == "Other"
    assert len(got) == 8


def test_a_condition_on_the_address_is_reported_never_guessed():
    for when in ("address", "address.postcode", "address.streetName"):
        built = run([[address(), comp("textfield", "t", conditional={"show": True, "when": when, "eq": "x"})]])
        got = questions(built)
        assert "logic" not in got[-1], when
        assert items(built, key="t", reason="condition_source_missing"), when


def test_a_rule_on_the_address_in_logic_is_reported_never_guessed():
    trigger = eq("address.postcode", "1234AB")
    built = run([[address(), comp("textfield", "t")]], logic=[rule(trigger, hide("t"))])
    assert "logic" not in questions(built)[-1]
    assert items(built, key="t", reason="condition_source_missing")


def test_a_rule_that_hides_the_address_hides_all_five():
    built = run(
        [[comp("radio", "r", values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]), address()]],
        logic=[rule(eq("r", "a"), hide("address"))],
    )
    got = questions(built)[1:]
    assert len(got) == 5 and all(q["logic"]["action"] == "HIDE" for q in got)
    assert {c["source"] for q in got for c in q["logic"]["conditions"]} == {"r"}


def test_a_condition_on_the_address_component_itself_hides_all_five_only_by_its_own_when():
    built = run([[comp("textfield", "t"), address(conditional={"show": True, "when": "t", "eq": "x"})]])
    got = questions(built)[1:]
    assert all(q["logic"]["conditions"][0]["source"] == "t" for q in got)


# --------------------------------------------------------------- groups


def test_an_address_in_a_repeating_group_is_five_children():
    built = run([[comp("editgrid", "g", "People", components=[comp("textfield", "n"), address()])]])
    (group,) = questions(built)
    assert [c["title"] for c in group["children"]][1:] == [
        "Home – Street",
        "Home – House number",
        "Home – Addition",
        "Home – Postcode",
        "Home – Place",
    ]


# ------------------------------------------------------------------ caps


def test_the_five_questions_count_against_the_cap(no_deadline):
    n = limits.MAX_IMPORT_FIELDS // 5
    built = run([[address(f"a{i}", f"A{i}") for i in range(n)]])
    assert built.summary["fields"] == limits.MAX_IMPORT_FIELDS
    with pytest.raises(ImportRefused) as caught:
        run([[address(f"a{i}", f"A{i}") for i in range(n + 1)]])
    assert (caught.value.status, caught.value.code) == (422, "archive_too_complex")
    # one question short of the cap: four addresses' worth of room for one more
    built = run([[address(f"a{i}") for i in range(n - 1)] + [comp("textfield", f"t{i}") for i in range(5)]])
    assert built.summary["fields"] == limits.MAX_IMPORT_FIELDS


def test_a_build_of_many_addresses_stays_inside_the_work_budget(monkeypatch):
    from backend.app.services.open_formulieren import limits as lim

    monkeypatch.setattr(lim, "BUILD_SECONDS", 0.02)
    with pytest.raises(ImportRefused) as caught:
        run([[address(f"a{i}", f"A{i}") for i in range(lim.MAX_IMPORT_FIELDS // 5)]])
    assert caught.value.code == "archive_too_complex"


def test_hostile_text_in_the_label_never_reaches_the_titles():
    built = run([[address(label="<script>x()</script>Home" + "y" * 2000)]])
    titles = [q["title"] for q in questions(built)]
    assert all("<" not in t and len(t) <= limits.MAX_TITLE for t in titles)
    assert titles[0].startswith("x()Home") or titles[0].startswith("Home")
