"""Exports of Open Formulieren 3.x: the same import, a few differences of
format, and every cap and the "nothing is executed" rule unchanged.

The 3.5.14 fixtures are our own exports of a local 3.5.14 instance
(tests/fixtures/open_formulieren/3.5.14/README.md). The older 3.x series we
read (3.2 to 3.4) have no fixture: they are covered by synthetic archives."""

import json
import os
import time

import pytest

from backend.app.container import container
from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.importer import build_draft
from backend.app.services.open_formulieren_import_service import _build
from backend.config import settings
from tests.app.open_formulieren.conftest import (
    CATASTROPHIC_SECONDS,
    FIXTURE_NAMES_3X,
    GOLDEN,
    archive_with,
    assert_scales_linearly,
    comp,
    describe,
    eq,
    exec_guard,  # noqa: F401  (fixture)
    fixture_bytes,
    hide,
    load,
    make_zip,
    no_deadline,  # noqa: F401  (fixture)
    rule,
)
from tests.app.open_formulieren.test_api import upload
from tests.app.open_formulieren.test_importer import items, questions, reasons
from tests.app.open_formulieren.test_review_fixes import _chain

RELEASE = "3.5.14"


def build(name: str):
    return build_draft(read_archive(fixture_bytes(name)))


def run3(steps, release=RELEASE, **kw):
    return build_draft(read_archive(archive_with(steps, version=release, **kw)))


def refusal3(steps, release=RELEASE, **kw):
    with pytest.raises(ImportRefused) as caught:
        run3(steps, release, **kw)
    return caught.value


# ---------------------------------------------------------------- fixtures


@pytest.mark.parametrize("name", FIXTURE_NAMES_3X)
def test_a_3x_fixture_imports_to_its_golden_form(name):
    actual = describe(build(name))
    path = GOLDEN / (name.removesuffix(".zip") + ".json")
    if os.environ.get("OF_UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n")
    assert actual == json.loads(path.read_text())


@pytest.mark.parametrize("name", FIXTURE_NAMES_3X)
def test_a_3x_fixture_names_its_release(name):
    archive = read_archive(fixture_bytes(name))
    assert archive.version == RELEASE and archive.series == (3, 5) and archive.is_3x
    assert archive.meta["of_git_sha"] == "92a999b1e2527d034a3cf84401e15f8113c585be"
    assert archive.ignored == []
    # a 3.x export has no form type and no help settings, and has the two
    # feature flags of its logic evaluation and renderer (4.0 dropped them)
    assert "type" not in archive.form and "help_dialog" not in archive.form
    assert {"new_logic_evaluation_enabled", "new_renderer_enabled"} <= set(archive.form)


@pytest.mark.parametrize("language", ["en", "nl"])
def test_the_same_form_from_3_5_14_and_4_0_6_imports_alike(language):
    """The content of the 3.5.14 and 4.0.6 sample forms is the same: what comes
    out is the same form with the same report."""
    old = describe(build(f"3.5.14/all-components.{language}.zip"))
    new = describe(build_draft(read_archive(fixture_bytes(f"all-components.{language}.zip"))))
    assert old == new


def test_structure_of_the_all_components_form():
    built = build("3.5.14/all-components.en.zip")
    assert built.summary == {"pages": 3, "fields": 27, "logicRules": 1, "repeatingGroups": 1, "dropped": 13, "flagged": 1}
    pages = describe(built)["pages"]
    assert [p["title"] for p in pages] == ["Contact details", "Choices and dates", "Extras"]
    types = {q["type"] for p in pages for q in p["questions"]}
    assert {"short_text", "long_text", "email", "number", "phone_number", "date", "dropdown", "multiple_choice", "yes_no", "file_upload", "text"} <= types
    assert [i["key"] for i in items(built, reason="national_identity_number")] == ["bsn"]
    assert [i["key"] for i in items(built, reason="unsupported_component_type")] == ["signature"]


def test_structure_of_the_logic_form():
    built = build("3.5.14/logic-variables.en.zip")
    assert built.summary["logicRules"] == 3
    assert sorted(i["detail"]["property"] for i in items(built, reason="custom_script_dropped")) == [
        "calculateValue", "customConditional", "customDefaultValue", "logic", "validate.custom",
    ]
    assert len(items(built, reason="user_variable_not_carried")) == 5
    assert items(built, reason="user_variable_calculated") == []
    assert {i["detail"]["actionType"] for i in items(built, reason="action_not_supported")} >= {"disable-next", "step-not-applicable", "variable"}


def test_structure_of_the_sign_in_payment_and_special_forms():
    built = build("3.5.14/signin-prefill-payment.en.zip")
    assert [i["detail"]["plugin"] for i in items(built, reason="sign_in_not_carried")] == ["digid"]
    assert [i["detail"]["plugin"] for i in items(built, reason="payment_not_carried")] == ["worldline"]
    assert len(items(built, reason="prefill_not_carried")) == 2
    assert [i["flag"] for i in built.report.items if i.get("flag")] == ["national_identity_number"]
    built = build("3.5.14/special-components.en.zip")
    assert sorted(i["detail"]["componentType"] for i in items(built, reason="unsupported_component_type")) == sorted(
        ["map", "partners", "children", "cosign", "customerProfile", "npFamilyMembers"]
    )
    assert [i["key"] for i in items(built, reason="converted_to_text") if i["detail"]["componentType"] == "addressNL"] == ["address"]
    assert [i["detail"]["plugin"] for i in items(built, reason="registration_not_carried")] == ["email"]


def test_a_3x_appointment_form_says_so_in_its_appointment_options():
    """A 3.x export has no form ``type``: the flag is in ``appointment_options``."""
    entries = load("3.5.14/appointment.en.zip")
    assert "type" not in entries["forms.json"][0]
    assert entries["forms.json"][0]["appointment_options"]["is_appointment"] is True
    assert reasons(build("3.5.14/appointment.en.zip"), kind="feature").count("appointment_not_carried") == 1
    other = load("3.5.14/all-components.en.zip")
    assert other["forms.json"][0]["appointment_options"]["is_appointment"] is False
    assert "appointment_not_carried" not in reasons(build("3.5.14/all-components.en.zip"))


def test_the_appointment_flag_is_read_only_from_a_3x_export():
    flag = {"appointment_options": {"is_appointment": True}}
    assert reasons(run3([[comp("textfield", "a")]], form=flag), kind="feature").count("appointment_not_carried") == 1
    assert "appointment_not_carried" not in reasons(run3([[comp("textfield", "a")]], "4.0.6", form=flag))
    # 4.0 states it as the form type
    assert "appointment_not_carried" in reasons(run3([[comp("textfield", "a")]], "4.0.6", form={"type": "appointment"}))
    # anything but a real true is not a flag
    for value in ("true", 1, None, [], {}):
        built = run3([[comp("textfield", "a")]], form={"appointment_options": {"is_appointment": value}})
        assert "appointment_not_carried" not in reasons(built)
    built = run3([[comp("textfield", "a")]], form={"appointment_options": "yes"})
    assert "appointment_not_carried" not in reasons(built)


# ------------------------------------------------------------------- logic


def test_a_rule_that_only_starts_from_a_step_is_dropped_and_the_others_stay():
    built = build("3.5.14/legacy-logic.en.zip")
    dropped = items(built, reason="trigger_not_supported")
    assert [(i["key"], i["detail"]) for i in dropped] == [("rule-1", {"cause": "trigger_from_step"})]
    assert dropped[0]["code"] == "dropped" and dropped[0]["severity"] == "warning"
    by_title = {q["title"]: q for q in questions(built)}
    assert by_title["Early note"]["logic"]["action"] == "HIDE"
    # the component that rule would have shown stays out, as an always hidden one does
    assert "Late note" not in by_title
    assert [i["key"] for i in items(built, reason="always_hidden")] == ["lateNote"]
    assert load("3.5.14/legacy-logic.en.zip")["forms.json"][0]["new_logic_evaluation_enabled"] is False


def test_trigger_from_step_only_counts_when_it_names_a_step():
    steps = [[comp("checkbox", "a"), comp("textfield", "t", hidden=True)]]

    def with_step(value, release=RELEASE):
        r = rule(eq("a", True), hide("t", False))
        if value != "absent":
            r["trigger_from_step"] = value
        return run3(steps, release, logic=[r])

    for value in (None, "", "absent"):
        built = with_step(value)
        assert reasons(built, kind="logic") == [] and built.summary["logicRules"] == 1
    for value in ("http://localhost/api/v2/forms/x/steps/y", "step", {"a": 1}, ["x"], 7, True):
        built = with_step(value)
        assert reasons(built, kind="logic") == ["trigger_not_supported"], value
        assert built.summary["logicRules"] == 0
    # 4.0 has no such key: whatever one holds is not looked at
    assert reasons(with_step("http://localhost/x", "4.0.6"), kind="logic") == []


def test_a_rule_with_the_3x_form_steps_list_is_read_like_any_other():
    r = rule(eq("a", True), hide("t", False))
    r["form_steps"] = ["http://localhost/api/v2/forms/f/steps/s"]
    built = run3([[comp("checkbox", "a"), comp("textfield", "t", hidden=True)]], logic=[r])
    assert reasons(built, kind="logic") == [] and built.summary["logicRules"] == 1


# ------------------------------------------------- shapes before release 3.5


def test_shapes_that_releases_before_3_5_wrote_are_read():
    """3.5 converts these when it upgrades a database; an export from an
    older release carries them as they were (docs/open-formulieren.md)."""
    built = build("3.5.14/pre35-shapes.en.zip")
    assert built.summary["fields"] == 7 and built.summary["logicRules"] == 2
    by_title = {q["title"]: q for q in questions(built)}
    # empty strings where a later release has null or no key
    entries = load("3.5.14/pre35-shapes.en.zip")
    components = {c["key"]: c for c in entries["formDefinitions.json"][0]["configuration"]["components"]}
    assert components["legacyText"]["conditional"] == {"show": "", "when": "", "eq": ""}
    assert components["legacyDate"]["datePicker"]["minDate"] == "" and components["legacyDate"]["openForms"]["minDate"] == {}
    assert components["legacyTime"]["validate"]["minTime"] == ""
    assert "logic" not in by_title["Legacy text"] and "dateRules" not in by_title["Legacy date"]
    # a condition on a choice and on a number written as text
    assert by_title["Legacy select"]["logic"]["conditions"] == [{"source": "Kind", "comparison": "IS_EQUAL", "value": "A"}]
    assert by_title["Legacy number"]["logic"]["conditions"] == [{"source": "Gate", "comparison": "IS_EQUAL", "value": 5}]
    assert "time" not in {i.get("detail", {}).get("property") for i in built.report.items}


@pytest.mark.parametrize(
    "extra",
    [
        {"conditional": {"show": "", "when": "", "eq": ""}},
        {"conditional": {"eq": ""}},
        {"conditional": {"show": None, "when": None, "eq": None}},
        {"conditional": {"show": True, "when": "", "eq": ""}},
        {"conditional": {"show": "", "when": "ghost", "eq": ""}},
        {"errors": {"required": "x"}, "translatedErrors": {"nl": {"maxLength": "a", "pattern": "b"}}},
        {"errors": "text"},
        {"openForms": {"translations": {"nl": {"label": "L", "defaultValue": "x"}}}},
        {"datePicker": {"minDate": "", "maxDate": ""}, "openForms": {"minDate": {}, "maxDate": {}}},
        {"datePicker": {"minDate": "", "maxDate": ""}, "openForms": {"minDate": {"mode": ""}, "maxDate": {"mode": ""}}},
        {"validate": {"minTime": "", "maxTime": ""}},
        {"defaultValue": None, "multiple": False},
    ],
)
@pytest.mark.parametrize("kind", ["textfield", "date", "time", "datetime", "select", "radio", "checkbox", "number"])
def test_an_older_empty_shape_never_breaks_the_import(kind, extra):
    component = comp(kind, "x", "X", **extra)
    if kind in ("select", "radio"):
        component["values" if kind == "radio" else "data"] = (
            [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]
            if kind == "radio"
            else {"values": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]}
        )
    built = run3([[component, comp("textfield", "keep")]], "3.3.4")
    assert built.summary["pages"] == 1 and built.summary["fields"] >= 1


# ------------------------------------------------------------- the releases


@pytest.mark.parametrize("release", ["3.2.0", "3.2.9", "3.3.0", "3.3.16", "3.4.0", "3.4.13", "3.5.0", "3.5.14", "3.5.99"])
def test_the_3x_series_we_read_are_accepted(release):
    archive = read_archive(archive_with([[comp("textfield", "a")]], version=release))
    assert archive.version == release and archive.is_3x
    assert archive.series == tuple(int(n) for n in release.split(".")[:2])
    assert build_draft(archive).summary["fields"] == 1


def test_4_0_is_not_taken_for_3x():
    archive = read_archive(archive_with([[comp("textfield", "a")]], version="4.0.6"))
    assert archive.series == (4, 0) and not archive.is_3x


@pytest.mark.parametrize("release", ["3.0.0", "3.0.9", "3.1.0", "3.1.9", "3.6.0", "3.10.0", "2.8.9", "4.1.0", "5.0.0"])
def test_the_other_series_are_refused_naming_the_release(release):
    with pytest.raises(ImportRefused) as caught:
        read_archive(archive_with([[comp("textfield", "a")]], version=release))
    error = caught.value
    assert (error.status, error.code) == (400, "open_formulieren_version_unsupported")
    assert error.extra == {"version": release, "supported": ["3.2", "3.3", "3.4", "3.5", "4.0"]}
    assert release in error.message and "3.2.x" in error.message and "4.0.x" in error.message


@pytest.mark.parametrize("value", ["3.5", "3", "3.5.14-rc.1", "3.5.14+x", "v3.5.14", "3.5.14\n", "3.5.x", "03.5.14x", "03.5.1", "3.05.1", "3.5.01", "\u0663.\u0665.\u0661\u0664", "\uff13.\uff15.\uff11\uff14", "3.5.1\u0664", 3.5, ["3.5.14"]])
def test_an_unreadable_3x_release_is_unknown_and_never_echoed(value):
    with pytest.raises(ImportRefused) as caught:
        read_archive(archive_with([[comp("textfield", "a")]], version=value))
    assert caught.value.code == "open_formulieren_version_unknown"
    assert "version" not in caught.value.extra and str(value) not in caught.value.message


def test_a_3x_archive_that_claims_a_4_0_release_is_read_as_4_0():
    """The series comes from ``_meta.json`` alone; what the archive claims is
    what is read (a 3.x flag in a 4.0 archive is not looked at)."""
    entries = load("3.5.14/appointment.en.zip")
    entries["_meta.json"]["of_release"] = "4.0.6"
    built = build_draft(read_archive(make_zip(entries)))
    assert "appointment_not_carried" not in reasons(built)


# ----------------------------------------------- caps and nothing executed


def test_custom_code_in_a_3x_archive_is_reported_never_carried_and_never_run(monkeypatch, tmp_path, exec_guard):
    marker = tmp_path / "ran"
    script = f"open({str(marker)!r}, 'w').write('x'); raise SystemExit(1)"
    scripted = comp(
        "textfield", "t", label="Scripted",
        customConditional=script,
        calculateValue="throw new Error('boom'); window.location='http://evil/'",
        customDefaultValue=script,
        validate={"custom": script, "customMessage": "<b>m</b>"},
        logic=[{"trigger": {"type": "javascript", "javascript": script}, "actions": []}],
    )
    rule_with_script = rule({"var": "t"}, hide("t"))
    rule_with_script["trigger_from_step"] = script  # a 3.x key holding code: only its presence counts
    calls = exec_guard
    built = run3([[scripted]], logic=[rule_with_script])
    assert not marker.exists() and calls == []
    got = sorted(i["detail"]["property"] for i in items(built, reason="custom_script_dropped"))
    assert got == ["calculateValue", "customConditional", "customDefaultValue", "logic", "validate.custom"]
    assert all(i["severity"] == "warning" for i in items(built, reason="custom_script_dropped"))
    text = json.dumps(describe(built)["pages"]) + built.form.model_dump_json()
    for needle in ("throw", "evil", "SystemExit", "customConditional", "calculateValue", "boom", str(marker)):
        assert needle not in text
    # the report names the property, never what it held
    report = json.dumps(built.report.items)
    for needle in ("throw", "evil", "SystemExit", "open(", str(marker)):
        assert needle not in report


def test_the_scripted_3x_fixture_is_reported_and_runs_nothing(exec_guard):
    built = build("3.5.14/logic-variables.en.zip")
    assert exec_guard == []
    assert len(items(built, reason="custom_script_dropped")) == 5


def test_markup_and_templates_in_a_3x_archive_stay_inert(exec_guard):
    hostile = comp(
        "textfield", "t",
        label="<img src=x onerror=alert(1)>{{ 7*7 }}{% load x %}<script>alert(1)</script>",
        description="<a href='javascript:alert(1)'>x</a> {{ public_reference }}",
    )
    built = run3([[hostile, comp("content", "c", html="<p onclick='x'>Hello {{ form.name }}</p><style>*{}</style>")]])
    text = json.dumps(describe(built)["pages"])
    for needle in ("<img", "<script", "onerror", "javascript:", "onclick", "<style", "<a "):
        assert needle not in text
    assert "{{ 7*7 }}" in text  # kept as literal text, never rendered
    assert exec_guard == []


def test_nothing_in_a_3x_archive_is_ever_fetched(monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("the import opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    data = load("3.5.14/legacy-logic.en.zip")
    data["forms.json"][0]["url"] = "http://169.254.169.254/latest/meta-data/"
    data["formSteps.json"][0]["url"] = "file:///etc/passwd"
    data["formLogic.json"][0]["trigger_from_step"] = "http://169.254.169.254/steps/x"
    data["formLogic.json"][0]["url"] = "http://169.254.169.254/rules/x"
    built = build_draft(read_archive(make_zip(data)))
    assert built.summary["pages"] == 2


def test_too_many_components_or_levels_in_a_3x_archive_are_too_complex(monkeypatch):
    monkeypatch.setattr(limits, "MAX_COMPONENTS", 10)
    error = refusal3([[comp("textfield", f"t{n}") for n in range(11)]])
    assert (error.status, error.code) == (422, "archive_too_complex")
    monkeypatch.setattr(limits, "MAX_COMPONENT_DEPTH", 3)
    deep = comp("textfield", "leaf")
    for n in range(5):
        deep = comp("fieldset", f"f{n}", components=[deep])
    assert refusal3([[deep]]).code == "archive_too_complex"


def test_too_many_steps_rules_or_variables_in_a_3x_archive_are_too_complex():
    for kw in (
        {"logic": [rule(eq("a", 1), hide("a"))] * (limits.MAX_LOGIC_RULES + 1)},
        {"variables": [{"key": f"v{n}", "source": "user_defined"} for n in range(limits.MAX_VARIABLES + 1)]},
    ):
        error = refusal3([[comp("textfield", "a")]], **kw)
        assert (error.status, error.code) == (422, "archive_too_complex")
    error = refusal3([[comp("textfield", "a")]] * (limits.MAX_STEPS + 1))
    assert (error.status, error.code) == (422, "archive_too_complex")


def test_a_3x_form_past_the_import_cap_is_refused_and_the_largest_is_built(no_deadline):
    n = limits.MAX_IMPORT_FIELDS
    _, built = _build(archive_with([_chain(n)], version=RELEASE))
    assert built.summary["fields"] == n and built.summary["logicRules"] == n - 1
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([_chain(n + 1)], version=RELEASE))
    assert (caught.value.status, caught.value.code) == (422, "archive_too_complex")


def test_a_3x_build_past_its_deadline_or_text_budget_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "BUILD_SECONDS", 0.02)
    started = time.monotonic()
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([_chain(limits.MAX_IMPORT_FIELDS)], version=RELEASE))
    assert caught.value.code == "archive_too_complex"
    assert time.monotonic() - started < 0.02 + 5
    monkeypatch.setattr(limits, "BUILD_SECONDS", 1e9)
    monkeypatch.setattr(limits, "MAX_TEXT_CHARS", 1_000)
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([[comp("textfield", f"t{n}", "x" * 200) for n in range(20)]], version=RELEASE))
    assert (caught.value.status, caught.value.code) == (422, "archive_too_complex")


def test_the_cost_of_a_big_3x_import_grows_with_its_size_and_not_faster(no_deadline):
    def make(n):
        data = archive_with([_chain(n)], version=RELEASE)
        return lambda: _build(data)

    assert_scales_linearly(make, 200, 400, factor=4.0, floor=0.5)


def test_hostile_json_inside_a_3x_archive_is_refused(monkeypatch):
    entries = load("3.5.14/all-components.en.zip")
    deep = ("[" * 100 + "]" * 100).encode()
    for name in ("formSteps.json", "formLogic.json", "formVariables.json", "formDefinitions.json", "forms.json"):
        with pytest.raises(ImportRefused) as caught:
            read_archive(make_zip({**entries, name: deep}))
        assert (caught.value.code, caught.value.extra["file"]) == ("archive_json_invalid", name)
    started = time.monotonic()
    with pytest.raises(ImportRefused) as caught:
        read_archive(make_zip({**entries, "formDefinitions.json": b"[" * 2_000_000 + b"]" * 2_000_000}))
    assert caught.value.code == "archive_json_invalid" and time.monotonic() - started < CATASTROPHIC_SECONDS
    monkeypatch.setattr(limits, "MAX_JSON_NODES", 1000)
    with pytest.raises(ImportRefused) as caught:
        read_archive(make_zip({**entries, "formLogic.json": b"[" + b"1," * 5000 + b"1]"}))
    assert caught.value.code == "archive_json_invalid"


def test_the_zip_limits_hold_for_a_3x_archive(monkeypatch):
    data = fixture_bytes("3.5.14/all-components.en.zip")
    entries = load("3.5.14/all-components.en.zip")
    with monkeypatch.context() as patch:
        patch.setattr(limits, "MAX_UPLOAD_BYTES", len(data) - 1)
        with pytest.raises(ImportRefused) as caught:
            read_archive(data)
        assert (caught.value.status, caught.value.code) == (413, "file_too_large")
    # a bomb: a few KB that unpack to more than an entry may hold, named like
    # an entry we read and like one we ignore
    for name in ("formVariables.json", "bomb.json"):
        bomb = make_zip({**entries, **({name: b"0" * (limits.MAX_ENTRY_BYTES + 1)})})
        with pytest.raises(ImportRefused) as caught:
            read_archive(bomb)
        assert caught.value.code == "archive_too_large", name
    # more entries than an export has
    many = make_zip(entries, extra={f"e{n}.txt": b"x" for n in range(limits.MAX_ENTRIES)})
    with pytest.raises(ImportRefused) as caught:
        read_archive(many)
    assert caught.value.code == "archive_too_large"
    # an unsafe name and a duplicate
    with pytest.raises(ImportRefused) as caught:
        read_archive(make_zip(entries, extra={"../forms.json": b"[]"}))
    assert caught.value.code == "archive_unsafe"
    # other safe names are ignored and listed, whatever the release
    assert read_archive(make_zip(entries, extra={"notes.txt": b"hi"})).ignored == ["notes.txt"]


# --------------------------------------------------------------------- HTTP


@pytest.mark.asyncio
async def test_a_3x_export_imports_over_http(client, workspace, test_user_cookies, import_on):
    name = "3.5.14/all-components.en.zip"
    response = await upload(client, workspace, test_user_cookies, fixture_bytes(name))
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["sourceKind"], body["sourceVersion"]) == ("open_formulieren", RELEASE)
    assert body["summary"] == {"pages": 3, "fields": 27, "logicRules": 1, "repeatingGroups": 1, "dropped": 13, "flagged": 1}
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert (link.settings.needs_review, link.settings.import_source) == (True, "open_formulieren")
    document = await container.form_repo().get_form_document_by_id(body["formId"])
    assert document.title == "Sample: all components"
    assert await container.form_repo().get_latest_version_of_form(body["formId"]) is None


@pytest.mark.asyncio
async def test_an_unsupported_3x_release_names_itself_and_counts_as_an_attempt(
    client, workspace, test_user_cookies, import_on, monkeypatch
):
    monkeypatch.setattr(settings.open_formulieren, "ATTEMPTS_PER_WORKSPACE_PER_DAY", 2)
    old = archive_with([[comp("textfield", "a")]], version="3.1.9")
    for _ in range(2):
        response = await upload(client, workspace, test_user_cookies, old)
        body = response.json()
        assert response.status_code == 400 and body["code"] == "open_formulieren_version_unsupported"
        assert body["version"] == "3.1.9" and body["supported"] == ["3.2", "3.3", "3.4", "3.5", "4.0"]
        assert "3.1.9" in body["message"]
    third = await upload(client, workspace, test_user_cookies, fixture_bytes("3.5.14/all-components.en.zip"))
    assert third.status_code == 429 and third.json()["code"] == "import_limit"
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []


@pytest.mark.asyncio
async def test_a_3x_import_is_still_behind_the_switch(client, workspace, test_user_cookies):
    data = fixture_bytes("3.5.14/all-components.en.zip")
    off = await upload(client, workspace, test_user_cookies, data)
    assert off.status_code == 410 and off.json()["code"] == "open_formulieren_off"
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []
