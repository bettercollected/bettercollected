"""Review fixes: a rename never overwrites content, the list reads columns only,
the budget and the checks that run before conversion, one atomic count, a stale
stored fragment is a 422, the edit operations resolve once per section and are
capped, and every surface that previews a batch resolves library sections."""

import asyncio
import json

import pytest
from common.models.standard_form import StandardForm
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.chat import persist_ops_to_form
from backend.app.services.ai.ops import parse_ops
from backend.app.services.ai.proposals import build_proposal
from backend.app.services.reusable_sections import fragment, limits, resolve
from backend.app.services.reusable_sections.service import (
    SectionContentDto,
    SectionDetailsDto,
)
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text
from tests.app.controllers.test_public_api import BASE, _auth, _create, _token
from tests.app.reusable_sections.helpers import form_with_page, make_section, q

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sections_on):
    pass


def service():
    return container.reusable_section_service()


def repo():
    return container.reusable_section_repo()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return error.content["code"] if isinstance(error.content, dict) else str(error.content)


# ------------------------------------------------------------------ S2: rename


async def test_a_rename_that_read_the_row_before_a_content_save_never_overwrites_it(workspace):
    created = await make_section(workspace, fields=[q("a", title="One")], containers=[])
    stale = await repo().get(workspace.id, created.id)
    # someone saves version 2 after the renamer read the row
    await service().save_content(
        workspace.id, created.id, SectionContentDto(fields=[q("a", title="Two"), q("b", title="Three")], containers=[]), testUser
    )
    stale.name, stale.name_key, stale.description = "Renamed", "renamed", "New note"
    await repo().replace(stale, None, bump=False)
    now = await repo().get(workspace.id, created.id)
    assert (now.name, now.description) == ("Renamed", "New note")
    assert now.version == 2 and now.question_count == 2
    assert [f["title"] for f in now.fields] == ["Two", "Three"]
    assert [v.version for v in now.history] == [1]


async def test_a_content_save_that_read_the_row_before_a_rename_keeps_the_rename(workspace):
    created = await make_section(workspace, fields=[q("a", title="One")], containers=[])
    stale = await repo().get(workspace.id, created.id)
    await service().update_details(workspace.id, created.id, SectionDetailsDto(name="Renamed", description="Note"), testUser)
    stale.fields = [dict(stale.fields[0], title="Two")]
    stale.version = 2
    await repo().replace(stale, 1, bump=True)
    now = await repo().get(workspace.id, created.id)
    assert (now.name, now.description, now.version) == ("Renamed", "Note", 2)
    assert now.fields[0]["title"] == "Two"


async def test_a_rename_and_a_content_save_at_once_lose_nothing(workspace):
    created = await make_section(workspace, fields=[q("a", title="One")], containers=[])
    await asyncio.gather(
        service().update_details(workspace.id, created.id, SectionDetailsDto(name="Renamed"), testUser),
        service().save_content(
            workspace.id, created.id, SectionContentDto(fields=[q("a", title="One"), q("b", title="Two")], containers=[]), testUser
        ),
    )
    now = await repo().get(workspace.id, created.id)
    assert now.name == "Renamed" and now.version == 2 and now.question_count == 2
    assert [v.version for v in now.history] == [1]


# ------------------------------------------------------- S3: the list and budget


async def test_the_list_reads_columns_only(workspace, monkeypatch):
    first = await make_section(workspace, name="B section", fields=[q("a")], containers=[])
    await make_section(workspace, name="A section", fields=[q("a"), q("b")], containers=[])

    async def boom(*args, **kwargs):  # the whole documents are never read
        raise AssertionError("the list read whole documents")

    monkeypatch.setattr(repo(), "many", boom)
    listed = await service().list_sections(workspace.id, testUser)
    assert [(s.name, s.question_count, s.version) for s in listed] == [("A section", 2, 1), ("B section", 1, 1)]
    rows = await repo().list_summaries(workspace.id)
    assert set(rows[0]) == {"id", "name", "description", "version", "question_count", "updated_at"}
    assert first.id in {s.id for s in listed}


async def test_the_workspace_library_has_a_byte_budget(workspace, monkeypatch):
    await make_section(workspace, name="One", fields=[q("a", title="x" * 200)], containers=[])
    used = await repo().content_bytes(workspace.id)
    assert used > 200
    monkeypatch.setattr(limits, "WORKSPACE_BYTES_MAX", used + 100)
    error = await refused(make_section(workspace, name="Two", fields=[q("a", title="y" * 200)], containers=[]))
    assert error.status_code == 422 and code_of(error) == "limit_reached"
    # a save of a new version counts too
    one = (await service().list_sections(workspace.id, testUser))[0]
    error = await refused(
        service().save_content(workspace.id, one.id, SectionContentDto(fields=[q("a", title="z" * 300)], containers=[]), testUser)
    )
    assert error.status_code == 422


async def test_concurrent_creates_cannot_pass_the_section_limit(workspace, monkeypatch):
    monkeypatch.setattr(limits, "SECTIONS_PER_WORKSPACE", 2)
    results = await asyncio.gather(
        *[make_section(workspace, name=f"S{n}", fields=[q("a")], containers=[]) for n in range(6)],
        return_exceptions=True,
    )
    made = [r for r in results if not isinstance(r, Exception)]
    assert len(made) == 2
    assert all(isinstance(r, HTTPException) and code_of(r) == "limit_reached" for r in results if isinstance(r, Exception))
    assert await repo().count(repo().row.workspace_id == str(workspace.id)) == 2


# ------------------------------------------- nits: checks before the conversion


async def test_size_count_and_depth_are_checked_before_anything_is_converted(workspace, monkeypatch):
    created = await make_section(workspace, fields=[q("a")], containers=[])

    def not_called(*args, **kwargs):
        raise AssertionError("converted before the checks")

    monkeypatch.setattr(fragment, "from_builder", not_called)
    big = await refused(make_section(workspace, fields=[q("a", title="x" * (limits.CONTENT_BYTES_MAX * 2))], containers=[]))
    assert big.status_code == 413
    many = await refused(make_section(workspace, fields=[q(f"q{n}") for n in range(limits.QUESTIONS_PER_SECTION + 1)], containers=[]))
    assert many.status_code == 422 and code_of(many) == "limit_reached"
    deep = q("leaf")
    for n in range(limits.NESTING_MAX + 1):
        deep = q(f"g{n}", "group", "G", fields=[deep])
    nested = await refused(make_section(workspace, fields=[deep], containers=[]))
    assert nested.status_code == 422 and "nest" in nested.content["message"]
    # the update plan checks the same before it reads the copy
    from backend.app.services.reusable_sections.service import PlanRequestDto

    error = await refused(
        service().update_plan(
            workspace.id,
            created.id,
            PlanRequestDto(instance="i", fields=[q(f"q{n}") for n in range(limits.QUESTIONS_PER_SECTION + 1)]),
            testUser,
        )
    )
    assert error.status_code == 422


async def test_a_stored_fragment_the_model_no_longer_reads_is_a_422_not_a_500(workspace):
    created = await make_section(workspace, fields=[q("a")], containers=[])
    stored = await repo().get(workspace.id, created.id)
    stored.fields = [{"id": "a", "type": "not_a_type_any_more", "title": "A"}]
    await repo().replace(stored, None, bump=True)
    error = await refused(service().get_section(workspace.id, created.id, testUser))
    assert error.status_code == 422 and code_of(error) == "section_invalid"


# ------------------------------------------------------- S5: the operations


def library_op(section_id, page="s1", **extra):
    return {"op": "insert_library_section", "pageId": page, "sectionId": section_id, **extra}


async def _form(workspace):
    form_doc = await form_with_page(workspace)
    document = await container.form_service().get_form_document_by_id(form_doc.form_id)
    return form_doc, document, StandardForm(**document.model_dump())


async def test_a_section_named_by_several_ops_is_read_once(workspace, monkeypatch):
    created = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    _, document, form = await _form(workspace)
    reads = []
    original = repo().get

    async def counting(workspace_id, section_id):
        reads.append(section_id)
        return await original(workspace_id, section_id)

    monkeypatch.setattr(repo(), "get", counting)
    ops = parse_ops([library_op(created.id) for _ in range(5)])
    new_form, results, _ = await persist_ops_to_form(document, form, ops, workspace_id=workspace.id, atomic=True)
    assert all(r.ok for r in results) and reads == [created.id]
    page = (await container.form_service().get_form_document_by_id(document.form_id)).fields[0].properties.fields
    ids = [f.id for f in page]
    # five copies, five sets of new ids
    assert len(ids) == 6 and len(set(ids)) == 6


async def test_too_many_library_operations_in_one_batch_are_refused_whole(workspace):
    created = await make_section(workspace, fields=[q("a")], containers=[])
    _, document, form = await _form(workspace)
    ops = parse_ops([library_op(created.id) for _ in range(limits.LIBRARY_OPS_PER_BATCH + 1)])
    error = await refused(persist_ops_to_form(document, form, ops, workspace_id=workspace.id))
    assert error.status_code == 422 and code_of(error) == "too_many_library_ops"
    stored = await container.form_service().get_form_document_by_id(document.form_id)
    assert len(stored.fields[0].properties.fields) == 1


async def test_a_section_that_exists_but_cannot_be_inserted_says_why(workspace, monkeypatch):
    created = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    _, document, form = await _form(workspace)
    # a switch turned off since the section was saved: a form could not take it now
    monkeypatch.setattr(settings, "NEW_QUESTION_TYPES_ENABLED", False)
    stored = await repo().get(workspace.id, created.id)
    stored.fields = [{"id": "x", "type": "currency", "title": "Amount"}]
    await repo().replace(stored, None, bump=True)
    ops = parse_ops([library_op(created.id), library_op("0" * 24)])
    _, results, _ = await persist_ops_to_form(document, form, ops, workspace_id=workspace.id)
    assert [r.ok for r in results] == [False, False]
    assert "cannot be inserted:" in results[0].message and "NEW_QUESTION_TYPES_ENABLED" in results[0].message
    # an unknown id keeps the message that does not say whether it exists elsewhere
    assert "does not exist in this workspace" in results[1].message
    assert "NEW_QUESTION_TYPES" not in results[1].message


# --------------------------------------------------- S4: every surface that previews


async def test_the_spec_dry_run_resolves_the_op(workspace):
    created = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    form_doc, _, form = await _form(workspace)
    response = await container.form_spec_service().preview_async(
        form, None, [library_op(created.id)], True, workspace_id=workspace.id
    )
    assert response.applied and response.results[0].op == "insert_library_section"
    assert "Alpha" in str(response.form)


async def test_the_public_api_dry_run_resolves_the_op(client: AsyncClient, workspace):
    section = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    token = await _token(workspace.id)
    created = await _create(client, token)
    form_id = created.json()["formId"]
    preview = await client.post(
        f"{BASE}/forms/{form_id}/ops/dry-run",
        json={"ops": [library_op(section.id, page="page-1")], "atomic": True},
        headers=_auth(token),
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["applied"] is True and body["results"][0]["op"] == "insert_library_section"
    assert "Alpha" in json.dumps(body["form"])
    # nothing was stored
    got = await client.get(f"{BASE}/forms/{form_id}", headers=_auth(token))
    assert "Alpha" not in got.text


async def test_the_mcp_dry_run_resolves_the_op(client: AsyncClient, workspace):
    section = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    form_doc, _, _ = await _form(workspace)
    token = await _make_key(workspace.id, ["forms:read", "forms:write"])
    result = await _call_tool(client, token, "dry_run_ops", {"form_id": str(form_doc.form_id), "ops": [library_op(section.id)], "atomic": True})
    body = _tool_text(result)
    assert body["applied"] is True and body["results"][0]["op"] == "insert_library_section"
    assert "Alpha" in json.dumps(body["form"])


async def test_the_ai_propose_mode_preview_resolves_the_op_and_keeps_the_op_as_written(workspace):
    created = await make_section(workspace, fields=[q("a", title="Alpha")], containers=[])
    _, _, form = await _form(workspace)
    ops = parse_ops([library_op(created.id)])
    fragments = await resolve.fetch_fragments(workspace.id, ops, service())
    preview_ops, _ = resolve.substitute(ops, fragments)
    proposal, results = build_proposal(form, None, ops, "Insert", "session", None, preview_ops)
    assert proposal is not None and results[0].ok and results[0].op == "insert_library_section"
    # what is kept to be accepted later is the op as the AI wrote it
    assert proposal.ops[0]["op"] == "insert_library_section"
    assert "Alpha" in str(proposal.form)
