"""The exporter: what an archive holds, the round trip through our own
importer, what is listed as not exported and what is never written."""

import copy
import datetime as dt
import json
import re
import zipfile

import pytest

from backend.app.services.open_formulieren import exporter, limits
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.exporter import (
    CHANGED,
    LEFT_OUT,
    R,
    build_export,
    export_filename,
)
from backend.app.services.open_formulieren.importer import build_draft
from tests.app.open_formulieren.conftest import FIXTURE_NAMES, FIXTURE_NAMES_3X, describe, fixture_bytes
from tests.app.open_formulieren.export_helpers import (
    INTERNAL_TITLE,
    built,
    by_key,
    choice,
    components,
    entries,
    form_of,
    kitchen_sink,
    q,
    slide,
    when,
)

NOW = dt.datetime(2026, 10, 27, 12, 0, 0, tzinfo=dt.timezone.utc)
# keys that would run code on their side; never written (their 4.0.6 has no
# UI or backend for them either: docs/open-formulieren.md)
SCRIPT_KEYS = {"customConditional", "calculateValue", "customDefaultValue", "custom", "logic"}


def export(form):
    return build_export(form, NOW)


def reasons(result, kind=None):
    return [(i.kind, i.reason) for i in result.items if kind in (None, i.kind)]


# ------------------------------------------------------------- the archive


def test_the_archive_has_the_six_entries_and_a_readme_in_a_fixed_order():
    result = export(kitchen_sink())
    with zipfile.ZipFile(__import__("io").BytesIO(result.data)) as archive:
        assert archive.namelist() == list(exporter.EXPORT_ENTRIES)
        assert all(i.compress_type == zipfile.ZIP_DEFLATED for i in archive.infolist())
        # plain files: no directories, no link or special-file mode
        assert {i.external_attr >> 16 for i in archive.infolist()} == {0o644}
    meta = entries(result.data)["_meta.json"]
    assert meta == {"of_release": "4.0.6", "of_git_sha": "", "created": NOW.isoformat()}


def test_the_archive_passes_our_own_hardened_reader():
    result = export(kitchen_sink())
    archive = read_archive(result.data)
    assert archive.version == "4.0.6"
    assert archive.ignored == [exporter.README_ENTRY]
    assert len(archive.form) and archive.logic and archive.variables == []


def test_uuids_are_deterministic_and_links_are_identifiers_only():
    a, b = export(kitchen_sink()), export(kitchen_sink())
    assert a.data == b.data  # same form, same moment, same bytes
    archive = entries(a.data)
    form = archive["forms.json"][0]
    assert form["url"].startswith("http://localhost/api/v2/forms/")
    urls = re.findall(r'"(https?://[^"]+)"', json.dumps(archive))
    assert urls and all(u.startswith("http://localhost/") for u in urls)
    # the form id of ours is never written (only hashed into the uuids)
    other = kitchen_sink()
    other.form_id = "6720a0c1e4b0c8a5f1d2e3f4"
    assert "6720a0c1e4b0c8a5f1d2e3f4" not in export(other).data.decode("latin-1")
    assert entries(export(other).data)["forms.json"][0]["uuid"] != form["uuid"]


def test_steps_are_our_pages_in_order_with_their_titles():
    archive = entries(export(kitchen_sink()).data)
    names = [d["name"] for d in archive["formDefinitions.json"]]
    # the page with only a staff-only question is not exported
    assert names == ["About you", "Choices", "Extras"]
    steps = archive["formSteps.json"]
    assert [s["index"] for s in steps] == [0, 1, 2]
    definitions = {d["uuid"] for d in archive["formDefinitions.json"]}
    assert {s["form_definition"].rsplit("/", 1)[-1] for s in steps} == definitions


def test_translations_hold_the_one_language_the_form_has():
    form = kitchen_sink()
    archive = entries(export(form).data)
    top = archive["forms.json"][0]
    assert top["translation_enabled"] is False
    # their import refuses a blank Dutch name
    assert top["translations"]["nl"]["name"] == "Kitchen sink"
    assert top["translations"]["en"]["name"] == "Kitchen sink"
    assert archive["formDefinitions.json"][0]["translations"]["nl"]["name"]
    untitled = form_of(slide("p", [q("a", "short_text", "A")]))
    names = [d["name"] for d in entries(export(untitled).data)["formDefinitions.json"]]
    assert names == ["Page 1"]
    dutch = form_of(slide("p", [q("a", "short_text", "A")]), settings={"language": "nl"})
    names = [d["name"] for d in entries(export(dutch).data)["formDefinitions.json"]]
    assert names == ["Pagina 1"]


def test_retention_days_become_the_removal_limit():
    archive = entries(export(kitchen_sink()).data)
    assert archive["forms.json"][0]["submissions_removal_options"] == {
        "successful_submissions_removal_limit": 30,
        "successful_submissions_removal_method": "delete_permanently",
    }
    page = slide("p", [q("a", "short_text", "A")])
    for settings, listed in (
        ({"response_expiration_type": "forever"}, False),
        ({"response_expiration_type": "date", "response_expiration": "2027-01-01"}, True),
        ({"response_expiration_type": "days", "response_expiration": "99999"}, True),
    ):
        result = export(form_of(copy.deepcopy(page), settings=settings))
        assert (
            entries(result.data)["forms.json"][0]["submissions_removal_options"] == {}
        )
        assert (LEFT_OUT, R.RETENTION) in reasons(result) or not listed


# ----------------------------------------------------------- the components


def test_every_question_type_becomes_its_component():
    comps = by_key(entries(export(kitchen_sink()).data))
    types = {key: c["type"] for key, c in comps.items()}
    assert types["yourName"] == "textfield"
    assert types["emailAddress"] == "email"
    assert types["phone"] == "phoneNumber"
    assert types["aboutYou"] == "textarea"
    assert types["age"] == "number"
    assert types["website"] == "textfield"
    assert types["plan"] == "radio"
    assert types["topics"] == "selectboxes"
    assert types["country"] == "select"
    assert types["newsletter"] == "checkbox"
    assert types["dateOfBirth"] == "date"
    assert types["attachment"] == "file"
    assert types["family"] == "editgrid"
    assert sorted(t for t in types.values() if t == "content")  # the statement
    name = comps["yourName"]
    assert name["validate"] == {"required": True, "plugins": [], "maxLength": 50, "pattern": "^[A-Za-z ]+$"}
    assert (name["description"], name["placeholder"], name["tooltip"]) == (
        "As on your passport", "Jane", "So we can greet you",
    )
    assert comps["age"]["validate"]["min"] == 0 and comps["age"]["validate"]["max"] == 120
    assert comps["topics"]["validate"]["minSelectedCount"] == 1
    assert comps["topics"]["validate"]["maxSelectedCount"] == 2
    assert [v["label"] for v in comps["plan"]["values"]] == ["Free", "Pro", "Team"]
    assert [v["label"] for v in comps["country"]["data"]["values"]] == [
        "Netherlands", "Belgium", "Germany",
    ]
    assert comps["family"]["groupLabel"] == "Member"
    assert comps["family"]["validate"] == {"required": True, "maxLength": 4}
    assert [c["key"] for c in comps["family"]["components"]] == ["memberName", "memberAge"]
    assert comps["attachment"]["useConfigFiletypes"] is True


def test_dates_carry_their_limits():
    comps = by_key(entries(export(kitchen_sink()).data))
    born = comps["dateOfBirth"]
    assert born["openForms"]["maxDate"] == {"mode": "past", "includeToday": True}
    # a strict "after" moves by a day: their limits include the date itself
    assert born["openForms"]["minDate"] == {"mode": "fixedValue"}
    assert born["datePicker"]["minDate"].startswith("1900-01-02")


def test_neighbours_with_a_width_are_packed_into_columns():
    comps = by_key(entries(export(kitchen_sink()).data))
    columns = [c for c in comps.values() if c["type"] == "columns"]
    assert len(columns) == 1
    assert [(c["size"], [x["label"] for x in c["components"]]) for c in columns[0]["columns"]] == [
        (6, ["First half"]), (6, ["Second half"]),
    ]


def test_keys_are_unique_and_never_shadow_their_static_variables():
    form = form_of(
        slide("p", [
            q("a", "short_text", "Name"), q("b", "short_text", "Name"),
            q("c", "short_text", "now"), q("d", "short_text", "auth_bsn"),
            q("e", "short_text", "123 go"), q("f", "short_text", "Ünïcode ñame"),
            q("g", "short_text", "!!!"),
        ], "P")
    )
    keys = [c["key"] for c in components(entries(export(form).data))]
    assert len(keys) == len(set(keys)) == 7
    assert "now" not in keys and "auth_bsn" not in keys
    assert all(re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", k) for k in keys)


def test_choices_have_safe_unique_values():
    form = form_of(
        slide("p", [
            q("a", "multiple_choice", "Pick", props={"allow_multiple_selection": True, "choices": [
                choice("1", "a.b"), choice("2", "A.B"), choice("3", "Zoë & co")]}),
        ], "P")
    )
    values = [v["value"] for v in by_key(entries(export(form).data))["pick"]["values"]]
    assert len(set(values)) == 3 and all(re.fullmatch(r"[a-z0-9-]+", v) for v in values)


# -------------------------------------------------------------------- rules


def test_a_single_equality_becomes_a_conditional_on_the_component():
    comps = by_key(entries(export(kitchen_sink()).data))
    assert comps["whyPro"]["conditional"] == {"show": True, "when": "plan", "eq": "pro"}
    # "hide unless it is Free" is "show when it is Free"
    assert comps["otherPlan"]["conditional"] == {"show": True, "when": "plan", "eq": "free"}
    # a yes/no answer is compared as a boolean
    assert comps["whyNot"]["conditional"] == {"show": True, "when": "newsletter", "eq": False}
    assert comps["whyPro"]["hidden"] is False


def test_other_comparisons_become_rules_as_data():
    archive = entries(export(kitchen_sink()).data)
    comps = by_key(archive)
    rules = {r["actions"][0]["component"]: r for r in archive["formLogic.json"]}
    assert set(rules) == {"guardianName", "combo"}
    guardian = rules["guardianName"]
    assert guardian["json_logic_trigger"] == {"<": [{"var": "age"}, 18]}
    assert guardian["is_advanced"] is False
    assert guardian["actions"][0]["action"] == {
        "type": "property", "property": {"value": "hidden", "type": "bool"}, "state": False,
    }
    assert comps["guardianName"]["hidden"] is True  # shown only by the rule
    combo = rules["combo"]
    assert combo["json_logic_trigger"] == {
        "and": [{"==": [{"var": "plan"}, "team"]}, {"==": [{"var": "topics.offers"}, True]}]
    }
    assert combo["is_advanced"] is True
    assert [r["order"] for r in archive["formLogic.json"]] == [0, 1]
    # every rule names the steps it touches, by link
    assert all(r["form_steps"] and r["form"].startswith("http://localhost/") for r in rules.values())


def test_hide_rules_leave_the_component_visible_until_they_fire():
    form = form_of(
        slide("p", [
            q("a", "number", "Amount"),
            q("b", "short_text", "Note", props={"logic": when("HIDE", "OR", ("a", "GREATER_THAN", 5), ("a", "IS_EMPTY", None))}),
        ], "P")
    )
    archive = entries(export(form).data)
    comp = by_key(archive)["note"]
    assert comp["hidden"] is False
    (rule,) = archive["formLogic.json"]
    assert rule["json_logic_trigger"] == {"or": [{">": [{"var": "amount"}, 5]}, {"==": [{"var": "amount"}, None]}]}
    assert rule["actions"][0]["action"]["state"] is True


def test_rules_that_do_not_fit_are_left_out_and_listed_never_guessed():
    result = export(kitchen_sink())
    comps = by_key(entries(result.data))
    # a text "contains" has no equivalent: the question stays visible
    assert comps["explain"]["conditional"] == {"eq": "", "show": None, "when": ""}
    assert comps["explain"]["hidden"] is False
    assert (LEFT_OUT, R.LOGIC_COMPARISON) in reasons(result)


def test_rules_inside_repeating_groups_or_on_hidden_sources_are_left_out():
    form = form_of(
        slide("p", [
            q("secret", "short_text", "Secret", internal=True),
            q("a", "short_text", "A"),
            q("b", "short_text", "B", props={"logic": when("SHOW", "AND", ("secret", "IS_EQUAL", "x"))}),
            q("c", "calculated", "C", props={"expression": {"var": "a"}}),
            q("d", "short_text", "D", props={"logic": when("SHOW", "AND", ("c", "IS_EQUAL", "x"))}),
            {"id": "g", "type": "group", "title": "G", "validations": {}, "properties": {
                "repeat": {"minItems": 1, "maxItems": 2}, "fields": [
                    q("g1", "short_text", "G1"),
                    q("g2", "short_text", "G2", props={"logic": when("SHOW", "AND", ("g1", "IS_EQUAL", "x"))}),
                ]}},
            q("e", "short_text", "E", props={"logic": when("SHOW", "AND", ("g1", "IS_EQUAL", "x"))}),
            q("f", "short_text", "F", props={"logic": when("SHOW", "AND", ("later", "IS_EQUAL", "x"))}),
            q("later", "short_text", "Later"),
        ], "P")
    )
    result = export(form)
    archive = entries(result.data)
    assert archive["formLogic.json"] == []
    assert all(
        c.get("conditional", {}).get("when", "") == "" and not c.get("hidden")
        for c in components(archive)
    )
    found = {r for _, r in reasons(result)}
    assert {R.LOGIC_SOURCE, R.LOGIC_GROUP, R.LOGIC_LATER} <= found


# ------------------------------------------------------ what is never written


def test_staff_only_questions_never_appear_anywhere_in_the_archive():
    result = export(kitchen_sink())
    blob = result.data
    with zipfile.ZipFile(__import__("io").BytesIO(blob)) as archive:
        everything = b"".join(archive.read(n) for n in archive.namelist()).decode("latin-1")
    assert "STAFFONLY" not in everything and INTERNAL_TITLE not in everything
    assert "Office use" not in everything
    # only their count is told, without a name
    readme = entries(blob)[exporter.README_ENTRY]
    assert "2 staff-only question(s) were left out" in readme


def test_nothing_executable_and_no_script_keys_are_ever_written():
    result = export(kitchen_sink())
    archive = entries(result.data)

    def keys(node):
        if isinstance(node, dict):
            for k, v in node.items():
                yield k
                yield from keys(v)
        elif isinstance(node, list):
            for item in node:
                yield from keys(item)

    assert not (SCRIPT_KEYS & set(keys(archive["formDefinitions.json"])))
    assert not (SCRIPT_KEYS & set(keys(archive["formSteps.json"])))
    # rules are data: operators of a fixed set, never a string to run
    allowed = {"==", "!=", ">", ">=", "<", "<=", "and", "or", "var"}
    for rule in archive["formLogic.json"]:
        stack = [rule["json_logic_trigger"]]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                assert set(node) <= allowed
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)


def test_hostile_text_stays_plain_text():
    form = form_of(
        slide("p", [
            q("a", "short_text", "<script>alert(1)</script>Name {{ secret }} {% if x %}",
              props={"description": "<img src=x onerror=alert(1)> {{field:abc|there}} {# c #}",
                     "placeholder": "<b>x</b>"}),
            q("b", "text", "Read <this> & {{ that }} 1 < 2\n\nSecond <script>x</script>"),
            q("c", "multiple_choice", "Pick", props={"choices": [choice("1", "<i>One</i> {{ x }}"), choice("2", "Two")]}),
        ], "<b>Page</b> {{ page }}")
    )
    result = export(form)
    # the README is a plain file nobody renders: only the archive's fields count
    blob = json.dumps({k: v for k, v in entries(result.data).items() if k != exporter.README_ENTRY})
    for text in ("<script", "onerror", "{{", "{%", "{#", "<img", "<b>", "<i>"):
        assert text not in blob, text
    comps = by_key(entries(result.data))
    statement = next(c for c in comps.values() if c["type"] == "content")
    assert statement["html"].count("<p>") == 2
    # tags are removed, a stray angle bracket and an ampersand are escaped
    assert statement["html"] == "<p>Read &amp; { { that }} 1 &lt; 2</p><p>Second</p>"
    labels = [c.get("label") for c in comps.values()]
    assert "Name { { secret }} { % if x %}" in labels


def test_a_title_with_answer_references_and_formatting_is_flattened_and_listed():
    title = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Hello ", "marks": [{"type": "bold"}]},
                {"type": "answerPipe", "attrs": {"kind": "field", "pipeKey": "x", "label": "your name"}},
            ]},
        ],
    }
    form = form_of(slide("p", [q("a", "short_text", title), q("b", "short_text", "B")], "P"))
    result = export(form)
    assert by_key(entries(result.data))["helloYourName"]["label"] == "Hello your name"
    assert {R.FORMATTING, R.PIPES} <= {r for _, r in reasons(result, CHANGED)}


def test_the_export_is_refused_when_it_would_be_empty_or_too_big(monkeypatch):
    only_internal = form_of(slide("p", [q("a", "short_text", "A", internal=True)], "P"))
    with pytest.raises(ImportRefused) as refused:
        export(only_internal)
    assert (refused.value.status, refused.value.code) == (422, "nothing_to_export")
    monkeypatch.setattr(exporter, "MAX_EXPORT_BYTES", 1000)
    with pytest.raises(ImportRefused) as refused:
        export(kitchen_sink())
    assert (refused.value.status, refused.value.code) == (422, "export_too_large")


def test_the_filename_is_ascii_whatever_the_title():
    for title in ('Ünïcode "quoted" ../../etc/passwd', "a\r\nSet-Cookie: x=1", "日本語", "", "x" * 400):
        name = export_filename(title)
        assert re.fullmatch(r"[a-z0-9-]{1,60}-open-formulieren\.zip", name), (title, name)
    assert export_filename("Annual survey 2026") == "annual-survey-2026-open-formulieren.zip"


# ---------------------------------------------------------- the readme


def lines_of(readme: str, heading: str):
    start = readme.index(heading)
    out = []
    for line in readme[start:].splitlines()[1:]:
        if not line.startswith("- "):
            break
        out.append(line)
    return out


def test_the_readme_lists_every_unmapped_item_and_the_count_matches():
    result = export(kitchen_sink())
    readme = entries(result.data)[exporter.README_ENTRY]
    left = lines_of(readme, "Left out (")
    changed = lines_of(readme, "Changed on the way (")
    assert len(left) + len(changed) == result.unmapped == len(result.items)
    assert f"Left out ({len(left)})" in readme and f"Changed on the way ({len(changed)})" in readme
    assert f"Items listed: {result.unmapped}" in readme
    text = "\n".join(left)
    assert '"Total": calculated fields were left out' in text
    assert '"Rate us": this question type has no equivalent' in text
    assert "page 2: page jump rules" in text
    assert '"Explain": a show/hide rule was left out' in text
    assert "page 4: nothing on this page could be exported" in text
    assert "2 staff-only question(s) were left out" in text
    assert "1 hidden URL-parameter field(s) were left out" in text
    assert "the privacy policy link was left out" in text
    changes = "\n".join(changed)
    assert '"Newsletter": \'required\' was not exported' in changes
    assert '"Website": a link question was exported as a text field' in changes
    assert '"Your name": the \'why we ask\' text was exported as the tooltip' in changes
    # the README never names a staff-only question
    assert "STAFFONLY" not in readme and "Office use" not in readme


def test_a_clean_form_lists_nothing():
    form = form_of(slide("p", [q("a", "short_text", "A"), q("b", "number", "B")], "P"))
    result = export(form)
    assert result.unmapped == 0
    readme = entries(result.data)[exporter.README_ENTRY]
    assert "Left out (0)\n- nothing" in readme and "Changed on the way (0)\n- nothing" in readme


# ---------------------------------------------------------- the round trip

# The differences the round trip may show, exactly: each is a documented
# change (docs/open-formulieren.md "Export"), nothing else may differ.
def after_the_trip(desc):
    """``describe`` of the original form, with the documented changes made."""
    desc = copy.deepcopy(desc)
    kept_pages = []
    for page in desc["pages"]:
        questions = []
        for question in page["questions"]:
            # left out: calculated and rating questions, staff-only questions
            if question["title"] in ("Total", "Rate us", INTERNAL_TITLE, "Office use"):
                continue
            questions.append(question)
            _lossy(question)
            for child in question.get("children", []):
                _lossy(child)
        if questions:
            page["questions"] = questions
            kept_pages.append(page)
    desc["pages"] = kept_pages
    return desc


def _lossy(question):
    # a required yes/no would mean "must be ticked" on a checkbox
    if question["type"] == "yes_no":
        question.get("validations", {}).pop("required", None)
        if not question.get("validations"):
            question.pop("validations", None)
    # a link question is a text field with a link pattern
    if question["title"] == "Website":
        question["type"] = "short_text"
        question["validations"] = {"regex": exporter.URL_PATTERN}
    # "why we ask" is the tooltip, which a re-import reads as the help text
    # when there is none
    if question["title"] == "Email address":
        question["description"] = "Needed for the receipt"
    # a strict "after" is the next day, inclusive
    for rule in question.get("dateRules", []):
        if rule["comparison"] == "after":
            rule["comparison"] = "on_or_after"
            rule["date"] = "1900-01-02"
    # a rule with no equivalent leaves the question visible
    if question["title"] == "Explain":
        question.pop("logic", None)
    _equivalent_logic(question)


def _equivalent_logic(question):
    """Rules that say the same thing in the other form: "contains" on a
    many-choice question is membership, and with one condition "show when
    not equal" is "hide when equal" (their one-line ``conditional`` can only
    say equal)."""
    logic = question.get("logic")
    if not logic:
        return
    for cond in logic["conditions"]:
        cond["comparison"] = {"CONTAINS": "IS_EQUAL", "DOES_NOT_CONTAIN": "IS_NOT_EQUAL"}.get(
            cond["comparison"], cond["comparison"]
        )
    if len(logic["conditions"]) == 1 and logic["conditions"][0]["comparison"] == "IS_NOT_EQUAL":
        logic["action"] = "SHOW" if logic["action"] == "HIDE" else "HIDE"
        logic["conditions"][0]["comparison"] = "IS_EQUAL"


def _normal(question):
    """What ``describe`` shows differently for no difference of substance: the
    importer always states ``required`` (our own forms leave it out when
    false), and orders date rules lower limit first."""
    question.setdefault("validations", {}).setdefault("required", False)
    if "dateRules" in question:
        question["dateRules"].sort(key=lambda r: r["comparison"])
    for child in question.get("children", []):
        _normal(child)
    return question


def normal(desc):
    for page in desc["pages"]:
        for question in page["questions"]:
            _normal(question)
    return desc


def roundtrip(form):
    result = export(form)
    again = build_draft(read_archive(result.data))
    return result, again


def strip(desc):
    desc = copy.deepcopy(desc)
    desc.pop("report"), desc.pop("summary")
    return desc


def test_a_round_trip_through_our_own_importer_changes_only_what_is_documented():
    form = kitchen_sink()
    result, again = roundtrip(form)
    expected = normal(after_the_trip(strip(describe(built(form)))))
    got = normal(strip(describe(again)))
    assert got["pages"] == expected["pages"]
    assert got["title"] == expected["title"] == "Kitchen sink"
    assert got["retention"] == expected["retention"] == ["days", "30"]
    # the counts the import reports are the counts the export made
    assert again.summary["pages"] == result.pages == 3
    assert again.summary["fields"] == result.questions
    assert again.summary["repeatingGroups"] == 1


def test_the_reimport_flags_nothing_that_the_export_did_not_say():
    _, again = roundtrip(kitchen_sink())
    reasons_ = {i["reason"] for i in again.report.items}
    # no component is dropped on the way back: they were all written to fit
    assert not {
        "unsupported_component_type", "unknown_component_type", "always_hidden",
        "trigger_not_supported", "action_not_supported", "conflicting_rules",
        "condition_source_missing", "condition_source_later", "custom_script_dropped",
        "rejected_by_form_rules", "empty_step", "empty_group",
    } & reasons_
    assert not [i for i in again.report.items if i.get("flag")]


@pytest.mark.parametrize("name", FIXTURE_NAMES + FIXTURE_NAMES_3X)
def test_every_fixture_survives_import_export_import(name):
    first = build_draft(read_archive(fixture_bytes(name)))
    result = export(first.form)
    second = build_draft(read_archive(result.data))
    a, b = normal(strip(describe(first))), normal(strip(describe(second)))
    for desc in (a, b):
        # the documented changes of these fixtures: a required checkbox, and a
        # calculated question (made from a variable) that the export leaves out
        for page in desc["pages"]:
            page["questions"] = [q for q in page["questions"] if q["type"] != "calculated"]
            for question in page["questions"]:
                _lossy_checkbox(question)
    assert a["pages"] == b["pages"]
    assert a["retention"] == b["retention"]
    assert result.unmapped <= 2


def _lossy_checkbox(question):
    if question["type"] == "yes_no":
        question.get("validations", {}).pop("required", None)
        if not question.get("validations"):
            question.pop("validations", None)


def test_every_logic_shape_survives_the_trip():
    form = form_of(
        slide("p", [
            q("t", "short_text", "Text"),
            q("n", "number", "Number"),
            q("d", "date", "Day"),
            q("y", "yes_no", "Yes no"),
            q("c", "multiple_choice", "One", props={"choices": [choice("1", "A"), choice("2", "B")]}),
            q("m", "multiple_choice", "Many", props={"allow_multiple_selection": True,
                                                     "choices": [choice("1", "X"), choice("2", "Y")]}),
            q("s1", "short_text", "S1", props={"logic": when("SHOW", "AND", ("t", "IS_EQUAL", "hi"))}),
            q("s2", "short_text", "S2", props={"logic": when("HIDE", "AND", ("t", "IS_NOT_EQUAL", "hi"))}),
            q("s3", "short_text", "S3", props={"logic": when("SHOW", "AND", ("t", "IS_EMPTY", None))}),
            q("s4", "short_text", "S4", props={"logic": when("HIDE", "AND", ("t", "IS_NOT_EMPTY", None))}),
            q("s5", "short_text", "S5", props={"logic": when("SHOW", "AND", ("n", "GREATER_THAN_EQUAL", 3))}),
            q("s6", "short_text", "S6", props={"logic": when("SHOW", "OR", ("n", "LESS_THAN", 3), ("n", "IS_EQUAL", 9))}),
            q("s7", "short_text", "S7", props={"logic": when("SHOW", "AND", ("d", "IS_EQUAL", "2026-01-01"))}),
            q("s8", "short_text", "S8", props={"logic": when("SHOW", "AND", ("y", "IS_EQUAL", "Yes"))}),
            q("s9", "short_text", "S9", props={"logic": when("HIDE", "AND", ("y", "IS_NOT_EQUAL", "Yes"), ("n", "IS_NOT_EMPTY", None))}),
            q("s10", "short_text", "S10", props={"logic": when("SHOW", "AND", ("c", "IS_EQUAL", "B"))}),
            q("s11", "short_text", "S11", props={"logic": when("SHOW", "AND", ("c", "IS_NOT_EQUAL", "B"), ("t", "IS_EQUAL", "go"))}),
            q("s12", "short_text", "S12", props={"logic": when("SHOW", "AND", ("m", "CONTAINS", "Y"))}),
            q("s13", "short_text", "S13", props={"logic": when("SHOW", "AND", ("m", "DOES_NOT_CONTAIN", "X"))}),
            q("s14", "short_text", "S14", props={"logic": when("SHOW", "AND", ("c", "IS_EMPTY", None))}),
        ], "P")
    )
    result, again = roundtrip(form)
    assert result.unmapped == 0, result.items
    expected = normal(strip(describe(built(form))))
    got = normal(strip(describe(again)))
    for question in expected["pages"][0]["questions"]:
        _equivalent_logic(question)
    assert got["pages"] == expected["pages"]


def test_a_form_the_importer_would_refuse_is_still_a_valid_export():
    # a form of statements and one question: nothing about the shape matters
    form = form_of(
        slide("a", [q("s", "text", "Intro")], "Only a statement"),
        slide("b", [q("q", "short_text", "Q")], "Q"),
    )
    result, again = roundtrip(form)
    assert again.summary["pages"] == 2 and result.questions == 1


def test_the_limits_of_our_reader_hold_for_the_biggest_form_we_allow():
    pages = [
        slide(f"p{n}", [q(f"q{n}_{i}", "short_text", f"Question {n} {i}") for i in range(20)], f"Page {n}")
        for n in range(1, 50)
    ]
    result = export(form_of(*pages))
    assert len(result.data) < limits.MAX_UPLOAD_BYTES
    archive = read_archive(result.data)
    assert len(archive.steps) == 49


# ------------------------------------------------------------ review fixes


def _every_string(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _every_string(value)
    elif isinstance(node, list):
        for item in node:
            yield from _every_string(item)


@pytest.mark.parametrize(
    "hostile",
    ["{{{ request.user }}}", "{{% debug %}", "{{# x #}}", "{%% if x %}", "{{{{ a }}}}", "{{ a }}", "{% a %}", "{# a #}"],
)
def test_overlapping_template_delimiters_cannot_survive(hostile):
    assert not re.search(r"\{[{%#]", exporter._neutral(hostile))
    form = form_of(
        slide("p", [
            q("a", "short_text", f"Name {hostile}", props={"description": hostile, "placeholder": hostile}),
            q("b", "multiple_choice", hostile, props={"choices": [choice("1", hostile), choice("2", "Two")]}),
            q("c", "text", f"Read {hostile}"),
        ], hostile),
        title=hostile,
    )
    archive = entries(export(form).data)
    # the README is a plain file nobody renders: only the archive's fields count
    for name in ("forms.json", "formSteps.json", "formDefinitions.json"):
        for text in _every_string(archive[name]):
            assert not re.search(r"\{[{%#]", text), (name, text)


def test_the_form_title_is_neutral_and_escaped_everywhere_it_is_written():
    form = form_of(slide("p", [q("a", "short_text", "A")]), title="Survey {{{ x }}} <b>& co</b> &lt;script&gt;")
    result = export(form)
    archive = entries(result.data)
    name = archive["forms.json"][0]["name"]
    assert name == "Survey { { { x }}} &amp; co &lt;script&gt;"
    assert "{{" not in name and "<" not in name
    top = archive["forms.json"][0]
    assert top["translations"]["nl"]["name"] == top["translations"]["en"]["name"] == name
    assert result.filename == "survey-x-co-open-formulieren.zip"
    assert re.fullmatch(r"[a-z0-9-]+\.zip", result.filename)


@pytest.mark.parametrize("raw", ["<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;", "&lt;img src=x onerror=alert(1)&gt;", "a < b > c & d"])
def test_decoded_entities_never_come_back_as_tags(raw):
    form = form_of(
        slide("p", [
            q("a", "short_text", raw, props={"description": raw, "placeholder": raw, "why_we_ask": raw}),
            q("b", "dropdown", "Pick", props={"choices": [choice("1", raw), choice("2", "Two")]}),
            q("c", "text", raw),
        ], raw),
        title=raw,
    )
    archive = entries(export(form).data)
    for name in ("forms.json", "formSteps.json", "formDefinitions.json"):
        for text in _every_string(archive[name]):
            # (a statement is written as escaped paragraphs: <p> and <br> only)
            assert not re.search(r"<[A-Za-z/!]", re.sub(r"</?p>|<br>", "", text)), (name, text)
    # and the importer reads the same text back
    again = build_draft(read_archive(export(form).data))
    assert again.summary["fields"] >= 1  # (a choice that is only a script has no text left)


def test_what_a_label_says_survives_the_escaping():
    form = form_of(slide("p", [q("a", "short_text", "Tom & Jerry's <3")], "P"))
    comp = next(c for c in components(entries(export(form).data)) if c["type"] == "textfield")
    assert comp["label"] == "Tom &amp; Jerry's &lt;3"
    again = build_draft(read_archive(export(form).data))
    assert again.form.fields[0].properties.fields[0].title == "Tom & Jerry's <3"


def test_escaped_names_still_fit_their_limits():
    name = "&" * 80
    form = form_of(slide("p", [q("a", "short_text", "A")], name), title="<" * 300)
    archive = entries(export(form).data)
    assert len(archive["formDefinitions.json"][0]["name"]) <= exporter.MAX_NAME
    assert len(archive["forms.json"][0]["name"]) <= exporter.MAX_FORM_NAME
    assert "&am" not in archive["formDefinitions.json"][0]["name"].replace("&amp;", "")


def test_a_form_the_importer_would_refuse_is_refused_before_any_work(monkeypatch):
    big = form_of(slide("p", [q(f"q{i}", "short_text", "Same") for i in range(limits.MAX_IMPORT_FIELDS + 1)], "P"))
    started = []
    monkeypatch.setattr(exporter.Exporter, "_plan", lambda *a, **k: started.append(1))
    with pytest.raises(ImportRefused) as refused:
        export(big)
    assert (refused.value.status, refused.value.code) == (422, "form_too_large_for_export")
    assert refused.value.extra["maxQuestions"] == limits.MAX_IMPORT_FIELDS
    assert started == []  # nothing was planned
    monkeypatch.undo()
    # staff-only questions are not counted: they are never exported
    padded = form_of(slide("p", [q("k", "short_text", "Keep")] + [q(f"i{i}", "short_text", "x", internal=True) for i in range(1500)], "P"))
    assert export(padded).questions == 1
    pages = [slide(f"p{n}", [q(f"q{n}", "short_text", "Q")], f"P{n}") for n in range(limits.MAX_STEPS + 1)]
    with pytest.raises(ImportRefused) as refused:
        export(form_of(*pages))
    assert refused.value.code == "form_too_large_for_export"


def test_the_biggest_form_we_export_is_exported_quickly_and_read_back():
    import time

    form = form_of(slide("p", [q(f"q{i}", "short_text", "Same") for i in range(limits.MAX_IMPORT_FIELDS)], "P"))
    started = time.monotonic()
    result = export(form)
    assert time.monotonic() - started < 3
    keys = [c["key"] for c in components(entries(result.data))]
    assert len(set(keys)) == len(keys) == limits.MAX_IMPORT_FIELDS
    assert keys[:3] == ["same", "same2", "same3"]
    assert build_draft(read_archive(result.data)).summary["fields"] == limits.MAX_IMPORT_FIELDS


@pytest.mark.parametrize(
    "pattern, risky",
    [
        (r"^[A-Za-z ]+$", False), (r"^[0-9]{9}$", False), (r"^(\d{3}-)?\d{4}$", False), (r"^(ab)+$", False),
        (r"^[(]+x", False), (r"\(+", False),
        (r"(a+)+$", True), (r"(a|a)*", True), (r"([a-z]+\s?)+$", True), (r"^((ab)|c)+$", True),
        (r"^(?=.*\d)\w+$", True), (r"(?<!x)a", True), (r"(a)\1", True), (r"(?P<n>a)(?P=n)", True),
    ],
)
def test_risky_patterns_are_recognised(pattern, risky):
    assert exporter.risky_pattern(pattern) is risky


def test_a_pattern_that_could_backtrack_is_left_out_and_listed_as_changed():
    form = form_of(
        slide("p", [
            q("a", "short_text", "Fine", rules={"regex": r"^[a-z]+$"}),
            q("b", "short_text", "Nested", rules={"regex": r"^(a+)+$"}),
            q("c", "short_text", "Look", rules={"regex": r"^(?=.*\d).+$"}),
            q("d", "short_text", "Bad", rules={"regex": "(unclosed"}),
        ], "P")
    )
    result = export(form)
    comps = by_key(entries(result.data))
    assert comps["fine"]["validate"]["pattern"] == r"^[a-z]+$"
    for key in ("nested", "look", "bad"):
        assert "pattern" not in comps[key]["validate"]
    listed = [i for i in result.items if i.reason == R.VALIDATION]
    assert [(i.kind, i.subject, i.detail) for i in listed] == [(CHANGED, s, "regex") for s in ("Nested", "Look", "Bad")]
