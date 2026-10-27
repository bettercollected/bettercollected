"""Fixes from the security review of the import: bounded work for hostile
text, the work budget and concurrency limit, number parsing that cannot
raise, quotas apart from the PDF import's, the upload part cap, and the
review mark kept from respondents."""

import asyncio
import time

import pytest

from backend.app.container import container
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren import numbers
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.importer import Planner, build_draft
from backend.app.services.open_formulieren.text import plain_text, strip_tags
from backend.app.services.open_formulieren_import_service import _build, _slots
from backend.config import settings
from tests.app.open_formulieren.conftest import archive_with, comp, fixture_bytes
from tests.app.open_formulieren.test_api import ROOT, upload, url
from tests.app.open_formulieren.test_importer import questions, reasons, run

# Python's own HTML parser needed 3 to 12 seconds for each of these (a few
# tens of KB); a linear scan needs milliseconds
HOSTILE_TEXT = [
    "<a " * 13_000,
    "<a b=" * 8_000,
    '<a b="' * 7_000,
    "<!--" * 20_000,
    "<script>" * 10_000,
    "<" * 40_000,
    "&" * 40_000,
    "<a>" * 13_000,
    "<script>x</script>" * 2_000,
    "<p>" + "x" * 40_000,
]


# ------------------------------------------------------------ text is linear


@pytest.mark.parametrize("text", HOSTILE_TEXT)
def test_hostile_markup_is_cheap(text):
    started = time.monotonic()
    plain_text(text, limits.MAX_STATEMENT)
    strip_tags(text)  # even uncut, the scan itself is linear
    assert time.monotonic() - started < 0.5


def test_a_small_archive_of_hostile_content_is_cheap_end_to_end():
    steps = [[comp("content", f"c{n}", html=text[:20_000]) for n, text in enumerate(HOSTILE_TEXT[:3])] + [comp("textfield", "keep")]]
    data = archive_with(steps)
    assert len(data) < 3_000
    started = time.monotonic()
    _build(data)
    assert time.monotonic() - started < 1.5


def test_tags_are_dropped_and_what_is_not_a_tag_is_kept():
    text, markup = strip_tags("a < b <3 <> <b>bold</b> <!-- x --> <script>evil()</script>tail <p>para")
    assert markup and "evil" not in text
    assert text.replace("\n", "") == "a < b <3 <> bold  tail para"
    # nothing after an unterminated tag, comment or element is text
    assert strip_tags("ok <a href=")[0] == "ok "
    assert strip_tags("ok <!-- never ends")[0] == "ok "
    assert strip_tags("ok <script>never ends")[0] == "ok "
    # entities are decoded after the cut, so an escaped tag stays text
    assert plain_text("&lt;b&gt;x&lt;/b&gt; &amp; y", 100) == ("<b>x</b> & y", False)


def test_the_input_is_cut_before_it_is_processed():
    text, _ = plain_text("a" * 10_000_000, 100)
    assert len(text) == 100


# ------------------------------------------------------------ work budget


def refused(**kw):
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([[comp("textfield", "a", "x" * 200) for _ in range(20)]], **kw))
    return caught.value


def test_text_beyond_the_budget_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "MAX_TEXT_CHARS", 1_000)
    error = refused()
    assert (error.status, error.code) == (422, "archive_too_complex")


def test_a_build_past_its_deadline_is_refused(monkeypatch):
    monkeypatch.setattr(limits, "BUILD_SECONDS", 0.0)
    error = refused()
    assert (error.status, error.code) == (422, "archive_too_complex")


def test_an_ordinary_form_is_within_the_budget():
    _, built = _build(fixture_bytes("all-components.en.zip"))
    assert built.summary["pages"] == 3


@pytest.mark.asyncio
async def test_only_a_few_imports_run_at_once(client, workspace, test_user_cookies, import_on):
    slots = _slots()
    for _ in range(limits.MAX_CONCURRENT_IMPORTS):
        await slots.acquire()
    try:
        response = await upload(client, workspace, test_user_cookies)
        assert response.status_code == 503
        assert response.json()["code"] == "import_busy"
        assert response.headers["retry-after"] == "5"
        assert await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren") == []
    finally:
        for _ in range(limits.MAX_CONCURRENT_IMPORTS):
            slots.release()
    assert (await upload(client, workspace, test_user_cookies)).status_code == 201


# ------------------------------------------------------------------- zip64
# (the zip64 archive is in test_archive.py)


# ------------------------------------------------------------ choices, numbers


def test_many_identical_choices_stay_distinct_and_cheap():
    options = [{"value": f"v{n}", "label": "Same"} for n in range(limits.MAX_CHOICES)]
    started = time.monotonic()
    built = run([[comp("radio", "r", values=options)]])
    assert time.monotonic() - started < 1
    choices = questions(built)[0]["choices"]
    assert len(set(choices)) == len(choices) == limits.MAX_CHOICES
    assert choices[:3] == ["Same", "Same (2)", "Same (3)"]


def test_a_label_that_looks_like_a_counter_does_not_collide():
    options = [{"value": v, "label": label} for v, label in (("a", "A"), ("b", "A (2)"), ("c", "A"), ("d", "A"))]
    choices = questions(run([[comp("radio", "r", values=options)]]))[0]["choices"]
    assert len(set(choices)) == 4 and choices[:2] == ["A", "A (2)"]


@pytest.mark.parametrize(
    "value, number, whole",
    [
        (10**400, None, None),
        (-(10**400), None, None),
        (float("inf"), None, None),
        (float("nan"), None, None),
        ("1e999", None, None),
        ("9" * 5000, None, None),
        ("²", None, None),
        ("٣", None, None),
        ("５", None, None),
        ("", None, None),
        (True, None, None),
        ([5], None, None),
        ("12", 12.0, 12),
        (" -7 ", -7.0, -7),
        (2.5, 2.5, None),
        (10**15, 1e15, 10**15),
        (10**15 + 1, None, None),
    ],
)
def test_numbers_from_the_file_never_raise(value, number, whole):
    assert numbers.to_number(value) == number
    assert numbers.to_int(value) == whole


def test_huge_and_odd_numbers_in_a_form_do_not_break_the_import():
    big = 10**400
    built = run(
        [
            [
                comp("number", "n", validate={"min": big, "max": "9" * 5000}),
                comp("number", "m", validate={"min": "²", "max": -big}),
                comp("textfield", "t", validate={"maxLength": "²"}),
                comp("textfield", "u", validate={"maxLength": big}),
                comp("editgrid", "g", validate={"maxLength": big}, components=[comp("textfield", "x")]),
                comp("selectboxes", "b", values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}], validate={"minSelectedCount": big}),
                comp("textfield", "cond", conditional={"show": True, "when": "n", "eq": big}),
            ]
        ],
        logic=[{"order": 0, "json_logic_trigger": {">": [{"var": "n"}, big]}, "actions": []}],
    )
    assert [q["title"] for q in questions(built)] == ["n", "m", "t", "u", "g", "b", "cond"]
    assert "min_value" not in questions(built)[0]["validations"]
    assert "trigger_not_supported" in reasons(built, kind="logic")


def test_an_unexpected_failure_is_a_refusal_not_a_server_error(monkeypatch):
    def boom(self):
        raise OverflowError("from the file")

    monkeypatch.setattr(Planner, "plan", boom)
    data = archive_with([[comp("textfield", "a")]])
    with pytest.raises(ImportRefused) as caught:
        build_draft(read_archive(data))
    assert (caught.value.status, caught.value.code) == (422, "archive_json_invalid")
    with pytest.raises(ImportRefused) as again:
        _build(data)
    assert again.value.code == "archive_json_invalid"
    assert "from the file" not in again.value.message


@pytest.mark.asyncio
async def test_an_unexpected_failure_answers_422_over_http(client, workspace, test_user_cookies, import_on, monkeypatch):
    monkeypatch.setattr(Planner, "plan", lambda self: (_ for _ in ()).throw(ValueError("x")))
    response = await upload(client, workspace, test_user_cookies, archive_with([[comp("textfield", "a")]]))
    assert response.status_code == 422 and response.json()["code"] == "archive_json_invalid"
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []


# ------------------------------------------------------------------ quotas


def _record(workspace, **kw):
    return FormImportDocument(
        workspace_id=workspace.id, form_id=None, created_by="u", status=ImportStatus.COMPLETED,
        file_name="f", content_type="x", size_bytes=1, sha256="0", source_key="k", **kw,
    )


@pytest.mark.asyncio
async def test_open_formulieren_imports_do_not_use_the_pdf_quota(workspace):
    repo = container.form_import_repo()
    for _ in range(25):
        await repo.save(_record(workspace, source_kind="open_formulieren"))
    pdf = await repo.save(_record(workspace))
    since = pdf.created_at.replace(year=pdf.created_at.year - 1)
    assert await repo.count_created_since(workspace.id, since) == 1  # the PDF import's own count
    assert await repo.count_created_since(workspace.id, since, kind="open_formulieren") == 25
    assert await repo.count_created_since(workspace.id, since, kind=None) == 26
    assert await repo.count_active(workspace.id) == 0
    # the PDF list is not crowded out by the others, and holds PDF imports only
    assert [r.id for r in await repo.list_by_workspace(workspace.id)] == [pdf.id]
    assert len(await repo.list_by_workspace(workspace.id, kind="open_formulieren")) == 20


@pytest.mark.asyncio
async def test_pdf_imports_do_not_count_against_the_open_formulieren_limit(
    client, workspace, test_user_cookies, import_on, monkeypatch
):
    monkeypatch.setattr(settings.open_formulieren, "IMPORTS_PER_WORKSPACE_PER_DAY", 1)
    await container.form_import_repo().save(_record(workspace))
    assert (await upload(client, workspace, test_user_cookies)).status_code == 201


@pytest.mark.asyncio
async def test_a_workspace_has_a_daily_limit_of_its_own(
    client, workspace, workspace_1, test_user_cookies, test_user_cookies_1, import_on, monkeypatch
):
    monkeypatch.setattr(settings.open_formulieren, "IMPORTS_PER_WORKSPACE_PER_DAY", 2)
    assert (await upload(client, workspace, test_user_cookies)).status_code == 201
    assert (await upload(client, workspace, test_user_cookies)).status_code == 201
    third = await upload(client, workspace, test_user_cookies)
    assert third.status_code == 429 and third.json()["code"] == "import_limit"
    assert len(await container.workspace_form_repo().list_in_workspace(workspace.id)) == 2
    # another workspace is not affected
    assert (await upload(client, workspace_1, test_user_cookies_1)).status_code == 201
    monkeypatch.setattr(settings.open_formulieren, "IMPORTS_PER_WORKSPACE_PER_DAY", 0)
    assert (await upload(client, workspace_1, test_user_cookies_1)).status_code == 429


# ------------------------------------------------------------- upload parts


@pytest.mark.asyncio
async def test_a_body_of_thousands_of_tiny_parts_is_stopped(client, workspace, test_user_cookies, import_on):
    boundary = "xBx"
    part = f'--{boundary}\r\nContent-Disposition: form-data; name="f"\r\n\r\n\r\n'
    body = (part * 40_000 + f"--{boundary}--\r\n").encode()
    started = time.monotonic()
    response = await client.post(
        url(workspace), cookies=test_user_cookies, content=body,
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert response.status_code == 400 and response.json()["code"] == "file_missing"
    assert time.monotonic() - started < 1.0


# ------------------------------------------------------------ semantics


def test_a_complete_conditional_decides_alone_and_hidden_only_counts_without_one():
    """Open Formulieren 4.0.6 (formio/visibility.py:59-62): with a complete
    conditional the ``hidden`` flag is not read; without one it is."""
    built = run(
        [
            [
                comp("checkbox", "c"),
                comp("textfield", "both", hidden=True, conditional={"show": True, "when": "c", "eq": True}),
                comp("textfield", "incomplete", hidden=True, conditional={"show": True, "when": "", "eq": True}),
                comp("textfield", "only_hidden", hidden=True),
            ]
        ]
    )
    titles = [q["title"] for q in questions(built)]
    assert titles == ["c", "both"]
    assert questions(built)[1]["logic"]["action"] == "SHOW"
    assert reasons(built, key="incomplete") == ["always_hidden"]
    assert reasons(built, key="only_hidden") == ["always_hidden"]


# ----------------------------------------------- the mark and respondents


def test_the_review_mark_is_not_in_what_respondents_see():
    from backend.app.models.dtos.response_dtos import FormSettingsCamelModel, StandardFormCamelModel
    from backend.app.services.internal_fields import respondent_view

    form = StandardFormCamelModel(
        title="t",
        settings=FormSettingsCamelModel(needs_review=True, import_source="open_formulieren", import_id="abc", purpose="why"),
    )
    seen = respondent_view(form).settings
    assert (seen.needs_review, seen.import_source, seen.import_id) == (None, None, None)
    assert seen.purpose == "why"  # what respondents do see stays


@pytest.mark.asyncio
async def test_the_public_read_of_an_imported_form_hides_the_mark(client, workspace, test_user_cookies, import_on):
    from backend.app.models.dtos.response_dtos import FormSettingsCamelModel, StandardFormCamelModel
    from backend.app.services.internal_fields import respondent_view

    body = (await upload(client, workspace, test_user_cookies)).json()
    link = await container.workspace_form_repo().find_workspace_form(workspace.id, body["formId"])
    assert link.settings.needs_review is True
    form = StandardFormCamelModel(title="t", settings=FormSettingsCamelModel(**link.settings.model_dump()))
    dumped = respondent_view(form).model_dump(by_alias=True)
    assert all(dumped["settings"][k] is None for k in ("needsReview", "importSource", "importId"))


# ======================================================= review fixes, round 2
# The engine's cost per operation grows with the form: the deadline is checked
# between operations, and the per-operation size count is opt-out.


def _chain(n, validate=True, kind="textfield"):
    out = []
    for i in range(n):
        c = comp(kind, f"f{i}", f"Field {i}")
        if validate and kind == "textfield":
            c["validate"] = {"maxLength": 50, "minLength": 2, "required": True}
        if i:
            c["conditional"] = {"show": True, "when": f"f{i - 1}", "eq": "x"}
        out.append(c)
    return out


def test_a_form_that_would_run_past_the_deadline_is_stopped_between_operations(monkeypatch):
    """Without a check between operations the build only noticed the deadline
    when it was over (17 s for 19 KB). The deadline is shortened here so the
    same shape stops quickly on any machine."""
    monkeypatch.setattr(limits, "BUILD_SECONDS", 0.2)
    started = time.monotonic()
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([_chain(1999)]))
    assert caught.value.code == "archive_too_complex"
    assert time.monotonic() - started < 1.5


def test_the_reported_shape_now_finishes_within_the_budget():
    """1999 questions, each with answer rules and a condition on the one
    before: the per-operation size walk made this 14 s, now it is linear."""
    started = time.monotonic()
    _, built = _build(archive_with([_chain(1999)]))
    elapsed = time.monotonic() - started
    assert built.summary["fields"] == 1999 and built.summary["logicRules"] == 1998
    assert elapsed < 4.5
    started = time.monotonic()
    _, built = _build(archive_with([_chain(1999, kind="date")]))
    assert time.monotonic() - started < 4.5


def test_a_legitimately_large_form_is_quick():
    steps = []
    for step in range(20):
        cs = []
        for k in range(50):
            n = step * 50 + k
            c = comp("textfield", f"f{n}", f"Field {n}", validate={"maxLength": 100, "required": k % 2 == 0})
            if k % 10 == 5 and n:
                c["conditional"] = {"show": True, "when": f"f{n - 1}", "eq": "x"}
            cs.append(c)
        steps.append(cs)
    started = time.monotonic()
    _, built = _build(archive_with(steps))
    assert built.summary["fields"] == 1000 and built.summary["logicRules"] == 100
    assert time.monotonic() - started < 2.5


def test_a_form_over_the_size_limits_is_refused_before_any_operation(monkeypatch):
    from backend.app.services.open_formulieren import importer

    monkeypatch.setattr(importer, "MAX_FIELDS", 10)
    with pytest.raises(ImportRefused) as caught:
        _build(archive_with([[comp("textfield", f"f{n}") for n in range(11)]]))
    assert caught.value.code == "archive_too_complex"
    monkeypatch.setattr(importer, "MAX_PAGES", 1)
    with pytest.raises(ImportRefused):
        _build(archive_with([[comp("textfield", "a")], [comp("textfield", "b")]]))


def test_apply_form_ops_keeps_its_size_checks_unless_asked_not_to(monkeypatch):
    from common.models.standard_form import StandardForm

    from backend.app.services.ai import ops as ops_module

    monkeypatch.setattr(ops_module, "MAX_FIELDS", 3)
    page = [{"op": "add_page", "ref": "p"}] + [
        {"op": "add_field", "pageId": "$ref:p", "field": {"title": f"Q{n}", "type": "short_text"}} for n in range(5)
    ]
    blank = StandardForm(title="t", fields=[])
    _, results = ops_module.apply_form_ops(blank, ops_module.parse_ops(page))
    assert not all(r.ok for r in results)  # the default: refused at the limit
    form, results = ops_module.apply_form_ops(blank, ops_module.parse_ops(page), check_size=False)
    assert all(r.ok for r in results) and len(form.fields[0].properties.fields) == 5


def test_a_run_of_combining_marks_is_cut_before_normalising():
    text = "a" + "́" * 5000 + "̖" * 5000 + "b"
    started = time.monotonic()
    for _ in range(20):
        out, _ = plain_text(text, 20_000)
    assert time.monotonic() - started < 0.5
    import unicodedata

    assert out.endswith("b") and len(unicodedata.normalize("NFD", out)) == 1 + 4 + 1
    # ordinary accents are untouched
    assert plain_text("école noël", 50)[0] == "école noë" + "l"


def test_a_huge_character_reference_does_not_cost_the_text():
    text = "before &#" + "9" * 6000 + "; after &#x" + "f" * 6000 + "; end &amp; ok"
    out, _ = plain_text(text, 20_000)
    assert out.startswith("before ") and "after" in out and out.endswith("end & ok")


def test_text_after_a_script_survives_a_character_that_changes_length_in_lower_case():
    # U+0130 lower-cases to two characters: positions found in a lower-cased
    # copy would be off for everything after it
    text = "İ" * 3 + "<script>x</script>tail <SCRIPT>y</SCRIPT>end"
    out, markup = strip_tags(text)
    assert out == "İ" * 3 + "tail end" and markup


def test_a_document_with_more_values_than_the_cap_is_refused_before_parsing(monkeypatch):
    from backend.app.services.open_formulieren.archive import parse_json

    monkeypatch.setattr(limits, "MAX_JSON_NODES", 1000)
    started = time.monotonic()
    with pytest.raises(ImportRefused) as caught:
        parse_json(b"[" + b"1," * 5000 + b"1]", "formSteps.json")
    assert caught.value.code == "archive_json_invalid"
    assert time.monotonic() - started < 0.1
    assert parse_json(b"[1, 2, 3]", "x") == [1, 2, 3]


@pytest.mark.asyncio
async def test_refused_archives_count_as_attempts(client, workspace, test_user_cookies, import_on, monkeypatch):
    monkeypatch.setattr(settings.open_formulieren, "ATTEMPTS_PER_WORKSPACE_PER_DAY", 3)
    for _ in range(3):
        refused_ = await upload(client, workspace, test_user_cookies, b"not a zip")
        assert refused_.status_code == 400 and refused_.json()["code"] == "not_a_zip"
    records = await container.form_import_repo().list_by_workspace(workspace.id, kind="open_formulieren")
    assert [(r.status, r.error_code, r.form_id, r.source_key) for r in records] == [("failed", "not_a_zip", None, "")] * 3
    # the fourth attempt, even a good archive, is held back until the day passes
    fourth = await upload(client, workspace, test_user_cookies)
    assert fourth.status_code == 429 and fourth.json()["code"] == "import_limit"
    assert await container.workspace_form_repo().list_in_workspace(workspace.id) == []


@pytest.mark.asyncio
async def test_refused_attempts_do_not_use_up_the_import_limit_and_are_per_workspace(
    client, workspace, workspace_1, test_user_cookies, test_user_cookies_1, import_on, monkeypatch
):
    monkeypatch.setattr(settings.open_formulieren, "ATTEMPTS_PER_WORKSPACE_PER_DAY", 5)
    monkeypatch.setattr(settings.open_formulieren, "IMPORTS_PER_WORKSPACE_PER_DAY", 1)
    await upload(client, workspace, test_user_cookies, b"x")
    await upload(client, workspace, test_user_cookies, b"x")
    assert (await upload(client, workspace, test_user_cookies)).status_code == 201  # failures are not imports
    assert (await upload(client, workspace, test_user_cookies)).status_code == 429  # one import a day
    assert (await upload(client, workspace_1, test_user_cookies_1)).status_code == 201
    # the PDF import's counts do not see any of it
    assert await container.form_import_repo().count_created_since(workspace.id, dt_year_ago()) == 0


def dt_year_ago():
    import datetime as dt

    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)
