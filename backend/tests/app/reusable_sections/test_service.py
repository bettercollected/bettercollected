"""A workspace's library of reusable sections: what is stored, versions, limits,
names, who may read and write, the switch, and that no section of another
workspace is ever found."""

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.reusable_sections import limits, refs
from backend.app.services.reusable_sections.service import (
    SectionContentDto,
    SectionCreateDto,
    SectionDetailsDto,
)
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.reusable_sections.helpers import (
    applicant_containers,
    applicant_fields,
    cond,
    make_section,
    q,
    show_if,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(sections_on):
    pass


def service():
    return container.reusable_section_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return error.content["code"] if isinstance(error.content, dict) else str(error.content)


async def test_a_section_is_stored_as_a_spec_fragment_with_its_own_ids(workspace):
    created = await make_section(workspace)
    assert created.version == 1 and created.question_count == 10
    stored = await container.reusable_section_repo().get(workspace.id, created.id)
    ids = refs.question_ids(stored.fields)
    # fresh ids of its own: none of the ids the builder used
    assert all(i.startswith("s") and len(i) == 17 for i in ids)
    assert not {"name", "age", "kind", "who"} & set(ids)
    by_title = {refs.plain_title(f): f for f in refs.questions(stored.fields)}
    age = by_title["Age"]
    assert age["logic"]["conditions"][0]["fieldId"] == by_title["Name"]["id"]
    assert age["validations"] == {"required": True}
    refs.assert_closed(stored.fields, stored.containers)
    assert stored.containers[0]["fields"] == [by_title["Name"]["id"], age["id"]]
    # a preview in the builder's shape
    shown = await service().get_section(workspace.id, created.id, testUser)
    assert [f["title"] for f in shown.fields][1] == "Age"
    assert shown.containers and shown.warnings == []


async def test_references_to_the_outside_are_dropped_with_warnings_on_save(workspace):
    fields = [
        q("a", title="A", logic=show_if(cond("elsewhere"))),
        q("b", "number", "B", rules=[{"id": "r", "when": {"conditions": [cond("elsewhere")]}, "then": {"required": True}}]),
        q("c", "calculated", "C", expression={"+": [{"var": "elsewhere"}, {"var": "b"}]}),
        q("d", "dropdown", "D", choices=[{"id": "x", "value": "x"}], optionSource=None, shareAsChoices=True),
    ]
    created = await make_section(workspace, fields=fields, containers=[])
    codes = sorted(w.code for w in created.warnings)
    assert codes == sorted(
        [
            refs.CONDITION_DROPPED,
            refs.RULE_DROPPED,
            refs.CALCULATION_LEFT_OUT,
            refs.SHARE_AS_CHOICES_DROPPED,
        ]
    )
    assert created.question_count == 3
    assert "Total" not in [f["title"] for f in created.fields]
    assert all(w.title for w in created.warnings)


async def test_a_form_answers_source_and_a_foreign_list_never_enter_a_section(
    workspace, workspace_1
):
    from backend.app.services.option_lists.service import ItemDto, OptionListCreateDto

    mine = await container.option_list_service().create_list(
        workspace.id, OptionListCreateDto(name="Mine", items=[ItemDto(label="x")]), testUser
    )
    theirs = await container.option_list_service().create_list(
        workspace_1.id, OptionListCreateDto(name="Theirs", items=[ItemDto(label="y")]), testUser1
    )
    fields = [
        q("a", "dropdown", "From my list", optionSource={"kind": "list", "listId": str(mine.id)}),
        q("b", "dropdown", "From their list", optionSource={"kind": "list", "listId": str(theirs.id)}),
        q("c", "dropdown", "From answers", optionSource={"kind": "form_answers", "formId": "f" * 24, "questionId": "q"}),
    ]
    created = await make_section(workspace, fields=fields, containers=[])
    by_title = {f["title"]: f for f in created.fields}
    assert by_title["From my list"]["properties"]["optionSource"]["listId"] == str(mine.id)
    assert by_title["From their list"]["properties"].get("optionSource") is None
    assert by_title["From answers"]["properties"].get("optionSource") is None
    assert sorted(w.code for w in created.warnings) == sorted(
        [refs.LIST_SOURCE_DROPPED, refs.FORM_ANSWERS_SOURCE_DROPPED]
    )


async def test_each_content_save_is_a_new_version_and_old_ones_stay_readable(workspace):
    created = await make_section(workspace, fields=[q("a", title="One")], containers=[])
    first_ids = [f["id"] for f in created.fields]
    saved = await service().save_content(
        workspace.id,
        created.id,
        SectionContentDto(fields=[q("a", title="One, changed"), q("b", title="Two")], containers=[], expected_version=1),
        testUser,
    )
    assert saved.version == 2 and saved.versions == [2, 1]
    old = await service().get_section(workspace.id, created.id, testUser, version=1)
    assert [f["title"] for f in old.fields] == ["One"] and old.version == 1
    assert [f["id"] for f in old.fields] == first_ids
    current = await service().get_section(workspace.id, created.id, testUser)
    assert [f["title"] for f in current.fields] == ["One, changed", "Two"]
    missing = await refused(service().get_section(workspace.id, created.id, testUser, version=7))
    assert missing.status_code == 404


async def test_a_save_made_after_someone_elses_is_a_conflict(workspace):
    created = await make_section(workspace, fields=[q("a")], containers=[])
    content = SectionContentDto(fields=[q("a"), q("b")], containers=[], expected_version=1)
    await service().save_content(workspace.id, created.id, content, testUser)
    error = await refused(service().save_content(workspace.id, created.id, content, testUser))
    assert error.status_code == 409 and code_of(error) == "section_changed"
    assert (await service().get_section(workspace.id, created.id, testUser)).version == 2


async def test_only_the_last_versions_are_kept(workspace):
    created = await make_section(workspace, fields=[q("a", title="v1")], containers=[])
    for n in range(2, limits.VERSIONS_KEPT + 3):
        await service().save_content(
            workspace.id, created.id, SectionContentDto(fields=[q("a", title=f"v{n}")], containers=[]), testUser
        )
    shown = await service().get_section(workspace.id, created.id, testUser)
    assert shown.version == limits.VERSIONS_KEPT + 2
    assert len(shown.versions) == limits.VERSIONS_KEPT
    assert (await refused(service().get_section(workspace.id, created.id, testUser, version=1))).status_code == 404


async def test_a_rename_is_not_a_new_version(workspace):
    created = await make_section(workspace)
    renamed = await service().update_details(
        workspace.id, created.id, SectionDetailsDto(name="  Person   details ", description=None), testUser
    )
    assert renamed.name == "Person details" and renamed.version == 1 and renamed.description is None
    other = await make_section(workspace, name="Other", fields=[q("a")], containers=[])
    clash = await refused(
        service().update_details(workspace.id, other.id, SectionDetailsDto(name="person DETAILS"), testUser)
    )
    assert clash.status_code == 409 and code_of(clash) == "name_taken"
    again = await refused(make_section(workspace, name="Person details", fields=[q("a")], containers=[]))
    assert again.status_code == 409


@pytest.mark.parametrize("name", ["", "   ", "a​b", "x" * 101])
async def test_a_bad_name_is_refused(workspace, name):
    error = await refused(make_section(workspace, name=name, fields=[q("a")], containers=[]))
    assert error.status_code == 422 and code_of(error) == "invalid_name"


async def test_limits(workspace, monkeypatch):
    empty = await refused(make_section(workspace, fields=[], containers=[]))
    assert empty.status_code == 422
    many = [q(f"q{n}") for n in range(limits.QUESTIONS_PER_SECTION + 1)]
    error = await refused(make_section(workspace, fields=many, containers=[]))
    assert error.status_code == 422 and code_of(error) == "limit_reached"
    ok = await make_section(workspace, name="Fifty", fields=many[:-1], containers=[])
    assert ok.question_count == limits.QUESTIONS_PER_SECTION
    monkeypatch.setattr(limits, "CONTENT_BYTES_MAX", 500)
    big = await refused(make_section(workspace, name="Big", fields=[q("a", title="x" * 600)], containers=[]))
    assert big.status_code == 413 and code_of(big) == "section_too_large"
    monkeypatch.setattr(limits, "SECTIONS_PER_WORKSPACE", 2)
    await make_section(workspace, name="Two", fields=[q("a")], containers=[])
    full = await refused(make_section(workspace, name="Three", fields=[q("a")], containers=[]))
    assert full.status_code == 422 and code_of(full) == "limit_reached"


async def test_a_section_that_a_form_could_not_take_is_refused(workspace, monkeypatch):
    monkeypatch.setattr(settings, "LAYOUT_CONTAINERS_ENABLED", False)
    error = await refused(make_section(workspace))
    assert error.status_code == 422 and code_of(error) == "layout_containers_disabled"
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    error = await refused(make_section(workspace, containers=[]))
    assert error.status_code == 422 and "field_rules" in code_of(error)
    # a broken fragment
    broken = [q("a", "calculated", "Calc", expression={"+": [{"var": "a"}, 1]})]
    error = await refused(make_section(workspace, fields=broken, containers=[]))
    assert error.status_code == 422 and code_of(error) == "invalid_section"


async def test_the_switch_off_makes_the_library_a_404(workspace, monkeypatch):
    created = await make_section(workspace)
    monkeypatch.setattr(settings, "REUSABLE_SECTIONS_ENABLED", False)
    for call in (
        service().list_sections(workspace.id, testUser),
        service().get_section(workspace.id, created.id, testUser),
        service().create_section(workspace.id, SectionCreateDto(name="x", fields=[q("a")]), testUser),
        service().delete_section(workspace.id, created.id, testUser),
        service().instantiate(workspace.id, created.id, testUser),
    ):
        assert (await refused(call)).status_code == 404


async def test_deleting_a_section_removes_only_the_section(workspace):
    created = await make_section(workspace, fields=[q("a")], containers=[])
    await service().delete_section(workspace.id, created.id, testUser)
    assert (await refused(service().get_section(workspace.id, created.id, testUser))).status_code == 404
    assert await service().list_sections(workspace.id, testUser) == []


# ------------------------------------------------------------------ who may


def _member(name):
    return User(id=str(RecordId()), sub=f"{name}@sections.example")


VIEWER, REVIEWER_USER, PRIVACY, EDITOR, ADMIN = (_member(n) for n in ("v", "r", "p", "e", "a"))
ROLE_USERS = [
    (VIEWER, WorkspaceRoles.VIEWER),
    (REVIEWER_USER, WorkspaceRoles.REVIEWER),
    (PRIVACY, WorkspaceRoles.PRIVACY_OFFICER),
    (EDITOR, WorkspaceRoles.EDITOR),
    (ADMIN, WorkspaceRoles.ADMIN),
]


@pytest.fixture()
async def roles(workspace):
    for user, role in ROLE_USERS:
        await container.workspace_user_repo().save(
            WorkspaceUserDocument(workspace_id=workspace.id, user_id=user.id, roles=[role])
        )


def url(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/sections{suffix}"


@pytest.mark.parametrize(
    "user,reads,writes",
    [
        (VIEWER, True, False),
        (REVIEWER_USER, True, False),
        (PRIVACY, True, False),
        (EDITOR, True, True),
        (ADMIN, True, True),
        (testUser1, False, False),  # not a member
    ],
)
async def test_reading_needs_form_read_and_everything_else_form_edit(
    client: AsyncClient, workspace, roles, user, reads, writes
):
    created = await make_section(workspace, fields=[q("a", title="A")], containers=[])
    cookies = _cookies(user)
    listed = await client.get(url(workspace), cookies=cookies)
    assert listed.status_code == (200 if reads else 403), listed.text
    one = await client.get(url(workspace, f"/{created.id}"), cookies=cookies)
    assert one.status_code == (200 if reads else 403)
    version = await client.get(url(workspace, f"/{created.id}?version=1"), cookies=cookies)
    assert version.status_code == (200 if reads else 403)
    body = {"name": f"By {user.sub}", "fields": [q("a", title="A")], "containers": []}
    post = await client.post(url(workspace), json=body, cookies=cookies)
    assert post.status_code == (201 if writes else 403), post.text
    content = await client.put(
        url(workspace, f"/{created.id}/content"),
        json={"fields": [q("a", title="A2")], "containers": []},
        cookies=cookies,
    )
    assert content.status_code == (200 if writes else 403), content.text
    patched = await client.patch(url(workspace, f"/{created.id}"), json={"name": "N"}, cookies=cookies)
    assert patched.status_code == (200 if writes else 403)
    inserted = await client.post(url(workspace, f"/{created.id}/instantiate"), cookies=cookies)
    assert inserted.status_code == (200 if writes else 403), inserted.text
    planned = await client.post(
        url(workspace, f"/{created.id}/update-plan"),
        json={"instance": "i", "fields": []},
        cookies=cookies,
    )
    assert planned.status_code in ((422,) if writes else (403,)), planned.text
    deleted = await client.delete(url(workspace, f"/{created.id}"), cookies=cookies)
    assert deleted.status_code == (204 if writes else 403)


async def test_a_section_of_another_workspace_is_never_found(
    client: AsyncClient, workspace, workspace_1
):
    mine = await make_section(workspace, name="Mine", fields=[q("a")], containers=[])
    theirs = await make_section(workspace_1, name="Theirs", fields=[q("a")], containers=[], user=testUser1)
    cookies = _cookies(testUser)
    for method, suffix, extra in (
        ("get", f"/{theirs.id}", {}),
        ("get", f"/{theirs.id}?version=1", {}),
        ("patch", f"/{theirs.id}", {"json": {"name": "Stolen"}}),
        ("put", f"/{theirs.id}/content", {"json": {"fields": [q("a")], "containers": []}}),
        ("post", f"/{theirs.id}/instantiate", {}),
        ("post", f"/{theirs.id}/update-plan", {"json": {"instance": "i", "fields": []}}),
        ("delete", f"/{theirs.id}", {}),
    ):
        response = await getattr(client, method)(url(workspace, suffix), cookies=cookies, **extra)
        assert response.status_code == 404, (method, suffix, response.text)
    other = f"/api/v1/workspaces/{workspace_1.id}/sections/{mine.id}"
    assert (await client.get(other, cookies=_cookies(testUser1))).status_code == 404
    assert (await service().get_section(workspace_1.id, theirs.id, testUser1)).name == "Theirs"
    for bad in ("nonsense", "0" * 24, "../" + "a" * 21):
        assert (await client.get(url(workspace, f"/{bad}"), cookies=cookies)).status_code in (404, 422)


async def test_an_unauthenticated_call_is_refused(client: AsyncClient, workspace):
    assert (await client.get(url(workspace))).status_code in (401, 403)


async def test_deleting_a_workspace_deletes_its_sections(workspace, workspace_1):
    mine = await make_section(workspace, name="Mine", fields=[q("a")], containers=[])
    theirs = await make_section(workspace_1, name="Theirs", fields=[q("a")], containers=[], user=testUser1)
    repo = container.reusable_section_repo()
    assert await repo.delete_for_workspaces([workspace.id]) == 1
    assert await repo.get(workspace.id, mine.id) is None
    assert await repo.get(workspace_1.id, theirs.id) is not None
    assert await repo.delete_for_workspaces([]) == 0
