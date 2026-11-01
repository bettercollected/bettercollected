"""The PDF of one submission: what it says (read back with a PDF text extractor),
that it is tagged, who may fetch it, the audit entry and what stays out of logs.
Everything here is synthetic."""

import datetime as dt
import io
import re

import pdfplumber
import pytest
from common.models.user import User
from common.records import RecordId
from httpx import AsyncClient
from loguru import logger
from pypdf import PdfReader

from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.response_export import ExportKind, ExportStatus
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.response_export import limits
from backend.app.services.response_export.table import ExportResponse
from backend.app.services.response_pdf import labels, render
from backend.app.services.response_pdf.content import build_document
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.response_export.helpers import (
    GROUP_FIELDS,
    answers,
    publish,
    start,
    submit,
)

pytestmark = pytest.mark.asyncio


def pdf_url(workspace, response_id, query: str = "") -> str:
    return f"/api/v1/workspaces/{workspace.id}/submissions/{response_id}/pdf{query}"


async def fetch_pdf(client: AsyncClient, workspace, response_id, query: str = "", user=testUser):
    return await client.get(pdf_url(workspace, response_id, query), cookies=_cookies(user))


def pages_text(data: bytes) -> str:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def audit(workspace, form):
    return container.response_export_repo().list_for_form(workspace.id, form.form_id)


def export_response(answers_: dict, **kwargs) -> ExportResponse:
    return ExportResponse(
        response_id=kwargs.pop("response_id", "resp-12345678"),
        responder=kwargs.pop("responder", "sita@example.org"),
        created_at=kwargs.pop("created_at", dt.datetime(2026, 11, 1, 21, 41, tzinfo=dt.timezone.utc)),
        answers=answers_,
        internal_answers=kwargs.pop("internal_answers", {}),
        hidden_fields=kwargs.pop("hidden_fields", {}),
        form_version=kwargs.pop("form_version", 2),
    )


def form_with(fields, title="Contact form", hidden=None) -> dict:
    return {
        "title": title,
        "form_id": "f1",
        "builder_version": "v2",
        "hidden_fields": hidden or [],
        "fields": [{"id": "s1", "type": "slide", "properties": {"fields": fields}}],
    }


def text(value):
    return {"type": "text", "text": value}


# ------------------------------------------------------------- the document


def test_the_language_and_the_time_zone_are_the_viewers():
    moment = dt.datetime(2026, 11, 1, 21, 41, tzinfo=dt.timezone.utc)
    assert labels.when(moment, "en", labels.zone("Europe/Amsterdam")) == "1 November 2026, 22:41 (CET)"
    assert labels.when(moment, "nl", labels.zone("Europe/Amsterdam")) == "1 november 2026 om 22:41 (CET)"
    # across midnight, and a zone without a letter abbreviation
    assert labels.when(moment, "en", labels.zone("Asia/Kolkata")) == "2 November 2026, 03:11 (IST)"
    assert labels.when(moment, "nl", labels.zone("America/New_York")) == "1 november 2026 om 16:41 (EST)"
    # an unknown, missing or hostile zone is UTC; an unknown language is English
    for bad in (None, "", "Mars/Olympus", "../../etc/passwd", "x" * 100, "UTC; DROP"):
        assert labels.when(moment, "en", labels.zone(bad)) == "1 November 2026, 21:41 (UTC)"
    assert [labels.language(v) for v in ("nl", "NL-be", "nl_NL", "en-GB", "de", None, "")] == ["nl", "nl", "nl", "en", "en", "en", "en"]


def test_a_document_has_the_title_facts_and_every_question_in_order():
    fields = [
        {"id": "a", "type": "short_text", "title": "First question"},
        {"id": "b", "type": "number", "title": "Second question"},
        {"id": "c", "type": "yes_no", "title": "Agree?"},
        {"id": "d", "type": "short_text", "title": "Unanswered"},
    ]
    document = build_document(
        form_with(fields, hidden=["utm_source", "utm_source", "empty"]),
        export_response({"a": text("Hello"), "b": {"type": "number", "number": 7}, "c": {"type": "boolean", "boolean": False}},
                        hidden_fields={"utm_source": "mail", "empty": ""}),
        "nl",
        "Europe/Amsterdam",
    )
    assert document.title == "Antwoord op Contact form" and document.lang == "nl"
    assert [(f.label, f.body) for f in document.facts] == [
        ("Ingediend", "1 november 2026 om 22:41 (CET)"),
        ("Respondent", "sita@example.org"),
        ("Antwoord-ID", "resp-12345678"),
        ("Formulierversie", "2"),
        ("utm_source", "mail"),
    ]
    entries = document.sections[0].entries
    assert [(e.label, e.body) for e in entries] == [
        ("First question", "Hello"),
        ("Second question", "7"),
        ("Agree?", "Nee"),
        ("Unanswered", "Geen antwoord"),
    ]
    assert entries[-1].muted and not entries[0].muted


def test_what_is_never_printed_stays_out():
    fields = [
        {"id": "a", "type": "short_text", "title": "Public"},
        {"id": "s", "type": "signature", "title": "Sign"},
        {"id": "f", "type": "file_upload", "title": "CV"},
        {"id": "i", "type": "short_text", "title": "Staff note", "internal": True},
    ]
    given = {
        "a": text("visible"),
        "s": {"type": "signature", "signature": {"method": "drawn", "file_id": "abc123", "signed_at": "2026-11-01T21:41:00Z"}},
        "f": {"type": "file_url", "file_url": "https://storage.example/o?sig=x", "file_metadata": {"id": "f", "name": "cv.pdf", "size": 12345, "url": "https://storage.example/o?sig=x"}},
    }
    document = build_document(
        form_with(fields), export_response(given, internal_answers={"i": text("secret staff note")}), "en", "Europe/Amsterdam"
    )
    everything = repr(document)
    assert "secret staff note" not in everything and "Staff note" not in everything
    assert "abc123" not in everything and "https://" not in everything and "sig=x" not in everything
    by_label = {e.label: e.body for e in document.sections[0].entries}
    assert by_label["CV"] == "cv.pdf (12 KB)"
    assert by_label["Sign"] == "Drawn signature (image not included)\nsigned 1 November 2026, 22:41 (CET)"


def test_a_typed_signature_prints_the_name_and_a_repeating_group_is_nested():
    form = form_with(GROUP_FIELDS_FOR_PDF)
    given = {
        "s": {"type": "signature", "signature": {"method": "typed", "name": "Sita Ram", "signed_at": "2026-11-01T21:41:00Z"}},
        "jobs": {"type": "group", "items": [
            {"employer": text("Acme\nBV"), "current": {"type": "boolean", "boolean": True}},
            {"employer": text("Globex")},
        ]},
        "plain": {"type": "group"},
    }
    entries = build_document(form, export_response(given), "en", "UTC").sections[0].entries
    by_label = {e.label: e for e in entries}
    assert by_label["Sign"].body == "Sita Ram\nTyped signature"
    assert "Plain group" not in by_label  # a group that is not repeating holds no answer of its own
    jobs = by_label["Jobs"].body
    assert [item.label for item in jobs] == ["Job 1", "Job 2"]
    assert [(e.label, e.body) for e in jobs[0].body] == [("Employer", "Acme\nBV"), ("Current", "Yes")]
    assert [(e.label, e.body) for e in jobs[1].body] == [("Employer", "Globex"), ("Current", "No answer")]
    empty = build_document(form, export_response({}), "en", "UTC").sections[0].entries
    assert {e.label: e.body for e in empty}["Jobs"] == "No answer"


GROUP_FIELDS_FOR_PDF = [
    {"id": "s", "type": "signature", "title": "Sign"},
    {"id": "plain", "type": "group", "title": "Plain group", "properties": {"fields": []}},
    {
        "id": "jobs",
        "type": "group",
        "title": "Jobs",
        "properties": {
            "repeat": {"min_items": 0, "max_items": 6, "item_label": "Job", "export_layout": "rows"},
            "fields": [
                {"id": "employer", "type": "short_text", "title": "Employer"},
                {"id": "current", "type": "yes_no", "title": "Current"},
            ],
        },
    },
]


# ------------------------------------------------------------------- the file


def render_of(fields, given, lang="en", tz="UTC", **kwargs) -> bytes:
    return render.render_pdf(build_document(form_with(fields, **kwargs), export_response(given), lang, tz))


def test_the_pdf_says_what_the_document_says():
    fields = [
        {"id": "a", "type": "short_text", "title": "Your name"},
        {"id": "b", "type": "long_text", "title": "Remarks"},
    ]
    data = render_of(fields, {"a": text("Zoë Łukasz Ω Привет"), "b": text("line one\nline two")}, "nl", "Europe/Amsterdam")
    assert data.startswith(b"%PDF-")
    body = pages_text(data)
    for expected in (
        "Antwoord op Contact form",
        "Ingediend 1 november 2026 om 22:41 (CET)",
        "Respondent sita@example.org",
        "Antwoorden",
        "Your name",
        "Zoë Łukasz Ω Привет",
        "line one",
        "line two",
        "Pagina 1 van 1",
    ):
        assert expected in body, expected


def test_markup_and_odd_characters_in_an_answer_are_text():
    nasty = "<b>bold</b> &amp; %(x)s ${y} {{z}} \x00\x07‮​ end \U0001f600 مرحبا"
    body = pages_text(render_of([{"id": "a", "type": "short_text", "title": "<i>Title</i> & more"}], {"a": text(nasty)}))
    assert "<i>Title</i> & more" in body
    assert "<b>bold</b> &amp; %(x)s ${y} {{z}}" in body
    # controls and format characters are dropped, characters the font lacks are U+FFFD
    assert "\x00" not in body and "‮" not in body and "​" not in body
    assert "end" in body and "�" in body


def test_a_long_answer_wraps_and_runs_over_pages_without_losing_a_word():
    words = [f"w{n:04d}" for n in range(3000)]
    data = render_of([{"id": "a", "type": "long_text", "title": "Essay"}], {"a": text(" ".join(words))})
    body = pages_text(data)
    assert len(PdfReader(io.BytesIO(data)).pages) >= 3
    found = re.findall(r"w\d{4}", body)
    assert found == words
    assert "Pagina" not in body and re.search(r"Page 1 of \d+", body)


def test_a_word_wider_than_the_line_is_broken_and_an_answer_over_the_cap_is_shortened():
    huge = "j" * 300
    body = pages_text(render_of([{"id": "a", "type": "short_text", "title": "Q"}], {"a": text(huge)}))
    assert body.replace("\n", "").count("j") == 300
    capped = "j" * (render.MAX_VALUE_CHARS + 500)
    body = pages_text(render_of([{"id": "a", "type": "long_text", "title": "Q"}], {"a": text(capped)}))
    assert body.replace("\n", "").count("j") == render.MAX_VALUE_CHARS and "[shortened]" in body


def test_the_pdf_is_tagged_in_reading_order():
    fields = [{"id": f"q{i}", "type": "short_text", "title": f"Question {i}"} for i in range(40)]
    data = render_of(fields, {f"q{i}": text(f"Answer {i}") for i in range(40)}, "nl", "Europe/Amsterdam")
    reader = PdfReader(io.BytesIO(data))
    catalog = reader.trailer["/Root"]
    assert catalog["/MarkInfo"]["/Marked"]
    assert str(catalog["/Lang"]) == "nl"
    assert catalog["/ViewerPreferences"]["/DisplayDocTitle"]
    assert reader.metadata.title == "Antwoord: Contact form"
    tree = catalog["/StructTreeRoot"]
    document = tree["/K"]
    assert document["/S"] == "/Document"
    roles = [kid["/S"] for kid in document["/K"]]
    assert roles[0] == "/H1" and "/L" in roles and "/H2" in roles
    # every list entry is Lbl + LBody, in the order the questions come
    answers_list = [kid for kid in document["/K"] if kid["/S"] == "/L"][-1]
    entries = answers_list["/K"]
    assert len(entries) == 40 and all(e["/S"] == "/LI" for e in entries)
    assert [k["/S"] for k in entries[0]["/K"]] == ["/Lbl", "/LBody"]
    # the marked content of the pages is reachable through the parent tree, once each
    nums = tree["/ParentTree"]["/Nums"]
    covered = sum(len(nums[i + 1]) for i in range(0, len(nums), 2))
    marked = sum(page.get_contents().get_data().count(b" BDC") - page.get_contents().get_data().count(b"/Artifact") for page in reader.pages)
    assert covered == marked > 0
    for index, page in enumerate(reader.pages):
        assert page["/StructParents"] == index
    # the footer is furniture, not content
    assert b"/Artifact" in reader.pages[0].get_contents().get_data()


def test_the_pdf_has_no_link_script_image_or_attachment():
    data = render_of([{"id": "a", "type": "url", "title": "Site"}], {"a": {"type": "url", "url": "https://evil.example/x?a=1"}})
    reader = PdfReader(io.BytesIO(data))
    for page in reader.pages:
        assert "/Annots" not in page
    catalog = reader.trailer["/Root"]
    assert "/Names" not in catalog and "/OpenAction" not in catalog and "/AcroForm" not in catalog and "/AA" not in catalog
    assert b"/JavaScript" not in data and b"/URI" not in data and b"/EmbeddedFile" not in data
    assert b"/XObject" not in data and b"/Subtype /Image" not in data
    # the URL is printed as plain text
    assert "https://evil.example/x?a=1" in pages_text(data)


def test_a_document_past_the_page_limit_is_refused(monkeypatch):
    monkeypatch.setattr(render, "MAX_PAGES", 2)
    fields = [{"id": f"q{i}", "type": "short_text", "title": f"Q{i}"} for i in range(200)]
    with pytest.raises(render.PdfTooLarge):
        render_of(fields, {f"q{i}": text("a") for i in range(200)})


# ------------------------------------------------------------------ the route


async def test_staff_fetch_the_pdf_of_a_response(client: AsyncClient, workspace):
    form = await publish(workspace, hidden=["utm_source"], title="Aanmelding")
    stored = await submit(workspace, form, answers("Ada Lovelace"), hidden={"utm_source": "mail"})
    response = await fetch_pdf(client, workspace, stored.response_id, "?lang=nl&tz=Europe/Amsterdam")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith('attachment; filename="Aanmelding - ')
    assert response.headers["content-disposition"].count(".pdf") >= 1
    assert response.content.startswith(b"%PDF-")
    body = pages_text(response.content)
    for expected in ("Antwoord op Aanmelding", "Ada Lovelace", "Full name", "Phone", "+31 6 1234", "30", "Red", "Blue", "utm_source mail", testUser.sub):
        assert expected in body, expected
    assert "Ingediend" in body and "(CET)" in body or "(CEST)" in body
    # English and UTC without parameters
    plain = pages_text((await fetch_pdf(client, workspace, stored.response_id)).content)
    assert "Response to Aanmelding" in plain and "Submitted" in plain and "(UTC)" in plain


async def test_the_pdf_is_never_stored_and_the_audit_entry_holds_no_content(client: AsyncClient, workspace):
    form = await publish(workspace, title="Secret title")
    stored = await submit(workspace, form, answers("Secretname"))
    response = await fetch_pdf(client, workspace, stored.response_id)
    assert response.status_code == 200
    (entry,) = await audit(workspace, form)
    assert entry.channel == "response_pdf" and entry.format == "pdf"
    assert entry.kind == ExportKind.STREAM and entry.status == ExportStatus.COMPLETED
    assert entry.actor_id == testUser.id and entry.row_count == entry.expected_rows == 1
    assert entry.filters == {"response_id": stored.response_id} and entry.columns == []
    assert entry.file_name is None and entry.chunk_count is None and entry.file_size is None
    dumped = repr(entry.model_dump(mode="json"))
    assert "Secretname" not in dumped and "Secret title" not in dumped and testUser.sub not in dumped
    assert await container.response_export_repo().count_chunks(str(entry.id)) == 0
    # the export routes do not list it: it is not a job
    listed = await client.get(f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/exports", cookies=_cookies(testUser))
    assert listed.json() == []


async def test_nothing_of_the_response_reaches_the_logs(client: AsyncClient, workspace, caplog):
    form = await publish(workspace, title="Hush title")
    stored = await submit(workspace, form, answers("Hushname"))
    seen = []
    sink = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    try:
        caplog.set_level("DEBUG")
        assert (await fetch_pdf(client, workspace, stored.response_id)).status_code == 200
    finally:
        logger.remove(sink)
    logged = "\n".join(seen) + "\n" + caplog.text
    assert "Hushname" not in logged and "Hush title" not in logged


@pytest.mark.parametrize(
    "role,allowed",
    [
        (WorkspaceRoles.ADMIN, True),
        (WorkspaceRoles.COLLABORATOR, True),
        (WorkspaceRoles.REVIEWER, True),
        (WorkspaceRoles.VIEWER, True),
        (WorkspaceRoles.PRIVACY_OFFICER, False),
    ],
)
async def test_the_permission_is_reading_the_response(client, workspace, role, allowed):
    other = User(id=str(RecordId()), sub="role@example.com")
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace.id, user_id=other.id, roles=[role])
    )
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))
    response = await fetch_pdf(client, workspace, stored.response_id, user=other)
    assert response.status_code == (200 if allowed else 403), response.text
    if not allowed:
        assert b"Ada" not in response.content
        assert await audit(workspace, form) == []
    else:
        assert len(await audit(workspace, form)) == 1


async def test_a_stranger_the_signed_out_and_an_unknown_response_get_nothing(client, workspace):
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))
    assert (await fetch_pdf(client, workspace, stored.response_id, user=testUser1)).status_code == 403
    assert (await client.get(pdf_url(workspace, stored.response_id))).status_code in (401, 403)
    missing = await fetch_pdf(client, workspace, "no-such-response")
    assert missing.status_code == 404 and b"Ada" not in missing.content
    assert await audit(workspace, form) == []


async def test_a_response_of_another_workspace_is_not_found(client, workspace):
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))
    other_workspace = type("W", (), {"id": str(RecordId())})()
    response = await fetch_pdf(client, other_workspace, stored.response_id)
    assert response.status_code in (403, 404) and b"Ada" not in response.content


async def test_the_pdf_shows_the_form_version_the_response_was_made_on(client: AsyncClient, workspace):
    form = await publish(workspace, title="Original title")
    stored = await submit(workspace, form, answers("Ada"))
    # a response that records its form version (an import does) is read against that version
    repo = container.form_response_repo()
    (row,) = await repo.list_by_response_id(stored.response_id)
    row.form_version = 1
    await repo.upsert(row)
    live = await container.form_repo().get_form_document_by_id(form.form_id)
    live.title = "Edited title"
    for field in live.fields[0].properties.fields:
        if field.id == "name":
            field.title = "Edited question"
    await container.form_repo().save_document(live)
    body = pages_text((await fetch_pdf(client, workspace, stored.response_id)).content)
    assert "Original title" in body and "Full name" in body
    assert "Edited title" not in body and "Edited question" not in body


async def test_the_pdf_has_its_own_budget_apart_from_the_exports(client, workspace, monkeypatch):
    monkeypatch.setattr(limits, "PDF_REQUESTS_PER_WINDOW", 2)
    monkeypatch.setattr(limits, "REQUESTS_PER_WINDOW", 1)
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))
    assert (await start(client, workspace, form)).status_code == 200
    assert (await start(client, workspace, form)).status_code == 429  # the export budget is spent
    for _ in range(2):
        assert (await fetch_pdf(client, workspace, stored.response_id)).status_code == 200
    refused = await fetch_pdf(client, workspace, stored.response_id)
    assert refused.status_code == 429 and refused.json()["code"] == "rate_limited"
    assert int(refused.headers["retry-after"]) >= 1
    # another person has their own
    assert (await fetch_pdf(client, workspace, stored.response_id, user=invited_user)).status_code in (200, 403)
    mine = [e for e in await audit(workspace, form) if e.channel == "response_pdf" and e.actor_id == testUser.id]
    assert len(mine) == 2


async def test_a_pdf_that_is_too_long_is_refused_and_still_uses_up_the_budget(client, workspace, monkeypatch):
    # its drawing cost the CPU: giving the request back would let refusals repeat for free
    monkeypatch.setattr(render, "MAX_PAGES", 1)
    monkeypatch.setattr(limits, "PDF_REQUESTS_PER_WINDOW", 1)
    form = await publish(workspace)
    stored = await submit(workspace, form, {"name": {"type": "text", "text": "word " * 4000}})
    refused = await fetch_pdf(client, workspace, stored.response_id)
    assert refused.status_code == 413 and refused.json()["code"] == "pdf_too_large"
    monkeypatch.setattr(render, "MAX_PAGES", 200)
    again = await fetch_pdf(client, workspace, stored.response_id)
    assert again.status_code == 429 and again.json()["code"] == "rate_limited"
    assert await audit(workspace, form) == []


async def test_a_pdf_whose_audit_entry_cannot_be_stored_is_not_handed_out(client, workspace, monkeypatch):
    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))

    async def broken(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(container.response_export_service()._exports, "save", broken)
    try:
        response = await fetch_pdf(client, workspace, stored.response_id)
    except RuntimeError:
        return  # the failure reached the test client: nothing was handed out
    assert response.status_code == 500 and b"%PDF" not in response.content


async def test_drawings_wait_for_a_free_slot_and_give_up_politely(client, workspace, monkeypatch):
    import asyncio

    form = await publish(workspace)
    stored = await submit(workspace, form, answers("Ada"))
    service = container.response_export_service()
    monkeypatch.setattr(limits, "PDF_WAIT_SECONDS", 0.05)
    held = [await service._pdf_slots.acquire() for _ in range(limits.PDF_PARALLEL)]
    try:
        busy = await fetch_pdf(client, workspace, stored.response_id)
        assert busy.status_code == 429 and busy.json()["code"] == "export_busy" and busy.headers["retry-after"] == "5"
    finally:
        for _ in held:
            service._pdf_slots.release()
    await asyncio.sleep(0)
    assert (await fetch_pdf(client, workspace, stored.response_id)).status_code == 200
    # the refused request was given back: nothing was recorded for it
    assert len(await audit(workspace, form)) == 1


async def test_a_hostile_form_title_cannot_split_the_header(client, workspace):
    form = await publish(workspace, title='Étude "2026"; a/b\r\nX-Evil: 1')
    stored = await submit(workspace, form, answers("Ada"))
    response = await fetch_pdf(client, workspace, stored.response_id)
    disposition = response.headers["content-disposition"]
    assert "\r" not in disposition and "\n" not in disposition and "x-evil" not in response.headers
    assert disposition.startswith("attachment; filename=") and "filename*=UTF-8''%C3%89tude" in disposition


# ------------------------------------------------- cost and the private hook


def test_an_unbroken_answer_is_wrapped_in_linear_time():
    import time

    started = time.monotonic()
    pieces = render.wrap("W" * render.MAX_VALUE_CHARS, render.REGULAR, render.BODY_SIZE, render.CONTENT_WIDTH)
    assert time.monotonic() - started < 1.0
    assert "".join(pieces) == "W" * render.MAX_VALUE_CHARS
    assert all(render.text_width(p, render.REGULAR, render.BODY_SIZE) <= render.CONTENT_WIDTH for p in pieces)
    # one character wider than a line is still one character per piece
    assert render.wrap("W", render.REGULAR, render.BODY_SIZE, 1.0) == ["W"]
    assert render.wrap("WW", render.REGULAR, render.BODY_SIZE, 1.0) == ["W", "W"]


def test_a_document_of_unbroken_answers_is_refused_quickly_not_laid_out_for_ever():
    import time

    fields = [{"id": f"q{i}", "type": "long_text", "title": f"Q{i}"} for i in range(60)]
    given = {f"q{i}": text("W" * render.MAX_VALUE_CHARS) for i in range(60)}
    started = time.monotonic()
    with pytest.raises(render.PdfTooLarge):
        render_of(fields, given)
    assert time.monotonic() - started < 5.0
    # 25 of them (500,000 characters) fit the character budget and still draw fast
    given = {f"q{i}": text("W" * render.MAX_VALUE_CHARS) for i in range(10)}
    started = time.monotonic()
    try:
        render_of(fields[:10], given)
    except render.PdfTooLarge:
        pass  # (the page cap may say so first)
    assert time.monotonic() - started < 5.0


def test_a_long_title_is_cut_for_the_footer_in_linear_time():
    import time

    render._ensure_fonts()  # registered by the first drawing otherwise
    started = time.monotonic()
    cut = render.ellipsize("W" * 200_000, render.REGULAR, render.FOOTER_SIZE, render.CONTENT_WIDTH - 90)
    assert time.monotonic() - started < 1.0
    assert cut.endswith("\u2026") and cut[:-1] == "W" * (len(cut) - 1)
    assert render.text_width(cut, render.REGULAR, render.FOOTER_SIZE) <= render.CONTENT_WIDTH - 90
    assert render.ellipsize("short", render.REGULAR, render.FOOTER_SIZE, 200) == "short"
    assert render.ellipsize("W", render.REGULAR, render.FOOTER_SIZE, 1.0) == "\u2026"


def test_a_form_title_of_any_length_draws_its_footer_quickly():
    import time

    fields = [{"id": f"q{i}", "type": "long_text", "title": f"Q{i}"} for i in range(8)]
    given = {f"q{i}": text("word " * 4000) for i in range(8)}
    started = time.monotonic()
    data = render_of(fields, given, title="T" * 10_000)
    assert time.monotonic() - started < 10.0
    assert len(PdfReader(io.BytesIO(data)).pages) > 20


def test_the_total_text_and_the_layout_time_are_bounded(monkeypatch):
    monkeypatch.setattr(render, "MAX_TOTAL_CHARS", 100)
    with pytest.raises(render.PdfTooLarge):
        render_of([{"id": "a", "type": "long_text", "title": "Q"}], {"a": text("x" * 500)})
    monkeypatch.setattr(render, "MAX_TOTAL_CHARS", 500_000)
    monkeypatch.setattr(render, "MAX_LAYOUT_SECONDS", -1.0)
    with pytest.raises(render.PdfTooLarge):
        render_of([{"id": "a", "type": "short_text", "title": "Q"}], {"a": text("x")})


def test_the_private_canvas_hook_still_exists():
    """Marked content is written through ``Canvas._code`` (no public hook): this
    fails when a ReportLab upgrade moves it, which is the signal to revisit
    ``render._draw`` (the version is pinned in pyproject.toml)."""
    import reportlab
    from reportlab.pdfgen import canvas

    assert reportlab.Version == "5.0.1"
    pdf = canvas.Canvas(io.BytesIO())
    assert isinstance(pdf._code, list)
    pdf._code.append("/P << /MCID 0 >> BDC")
    pdf.drawString(10, 10, "x")
    pdf._code.append("EMC")
    pdf.showPage()
    pdf.save()
