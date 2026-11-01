"""A workspace's option lists: limits, text rules, names, the revision check, CSV,
deleting a list a form uses, and who may read and write (and that no list of
another workspace is ever found)."""

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services.option_lists.service import (
    ItemDto,
    OptionListCreateDto,
    OptionListUpdateDto,
)
from backend.app.services.option_sources import text
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.option_sources.helpers import ids_of, make_list, publish, question

pytestmark = pytest.mark.asyncio


def service():
    return container.option_list_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return (
        error.content["code"] if isinstance(error.content, dict) else str(error.content)
    )


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


async def test_a_list_keeps_its_items_in_order_and_gives_each_an_id(workspace):
    created = await make_list(workspace)
    assert [i.label for i in created.items] == [
        "Amsterdam",
        "Utrecht",
        "Berlin",
        "Hamburg",
        "Anywhere",
    ]
    assert len({i.id for i in created.items}) == 5 and all(
        i.id.startswith("li") for i in created.items
    )
    assert created.revision == 1 and created.total_items == 5
    again = await service().get_list(workspace.id, created.id, testUser)
    assert [i.id for i in again.items] == [i.id for i in created.items]
    summaries = await service().list_lists(workspace.id, testUser)
    assert [(s.name, s.item_count, s.forms_using) for s in summaries] == [
        ("Cities", 5, 0)
    ]
    assert not hasattr(summaries[0], "items")


async def test_text_is_cleaned_and_bad_items_are_refused_with_their_row(workspace):
    created = await make_list(workspace, items=[("  Zoë \n van  Dam ", " Group  A ")])
    assert (created.items[0].label, created.items[0].group) == (
        "Zoë van Dam",
        "Group A",
    )
    cases = (
        ("", None),
        ("a\u200bb", None),
        ("x" * 201, None),
        ("ok", "g" * 201),
        ("ok", "a\x00"),
    )
    for index, (label, group) in enumerate(cases):
        error = await refused(
            make_list(
                workspace, name=f"List {index}", items=[("fine", None), (label, group)]
            )
        )
        assert (
            code_of(error) == "invalid_item"
            and error.content["row"] == 2
            and error.status_code == 422
        )
    # the same label and group twice (compared folded) is a duplicate; another group is not
    dup = await refused(
        make_list(workspace, name="D", items=[("Aa", "g"), (" aA", "G")])
    )
    assert code_of(dup) == "duplicate_item"
    await make_list(workspace, name="E", items=[("Aa", "g"), ("aA", "h"), ("aA", None)])


async def test_names_are_unique_per_workspace_compared_folded(workspace, workspace_1):
    await make_list(workspace, name="Cities")
    assert (
        code_of(await refused(make_list(workspace, name="  cities "))) == "name_taken"
    )
    assert code_of(await refused(make_list(workspace, name="​"))) == "invalid_name"
    # another workspace may use the name
    await make_list(workspace_1, name="Cities", user=testUser1)


async def test_the_limits_are_enforced(workspace, monkeypatch):
    big = [(f"item {n}", None) for n in range(text.ITEMS_PER_LIST + 1)]
    # the service's own check (the DTO caps the list too, so build it unvalidated)
    oversize = OptionListCreateDto.model_construct(
        name="Big", order="manual", items=[ItemDto(label=l, group=g) for l, g in big]
    )
    error = await refused(service().create_list(workspace.id, oversize, testUser))
    assert code_of(error) == "limit_reached"
    await make_list(workspace, name="Max", items=big[:-1])
    monkeypatch.setattr(text, "LISTS_PER_WORKSPACE", 2)
    from backend.app.services.option_lists import service as lists_module

    monkeypatch.setattr(lists_module.text, "LISTS_PER_WORKSPACE", 2)
    await make_list(workspace, name="Two")
    assert code_of(await refused(make_list(workspace, name="Three"))) == "limit_reached"


async def test_an_update_keeps_the_ids_of_kept_items_and_refuses_unknown_ids(workspace):
    created = await make_list(workspace)
    ids = ids_of(created)
    updated = await service().update_list(
        workspace.id,
        created.id,
        OptionListUpdateDto(
            name="Towns",
            order="alphabetical",
            items=[
                ItemDto(
                    id=ids["Utrecht"], label="Utrecht (renamed)", group="Netherlands"
                ),
                ItemDto(label="Paris", group="France"),
            ],
            expected_revision=1,
        ),
        testUser,
    )
    assert (
        updated.revision == 2
        and updated.name == "Towns"
        and updated.order == "alphabetical"
    )
    assert (
        updated.items[0].id == ids["Utrecht"]
        and updated.items[0].label == "Utrecht (renamed)"
    )
    assert updated.items[1].id not in ids.values()
    # an id the list does not have is never adopted
    error = await refused(
        service().update_list(
            workspace.id,
            created.id,
            OptionListUpdateDto(items=[ItemDto(id="li" + "0" * 22, label="X")]),
            testUser,
        )
    )
    assert code_of(error) == "unknown_item"
    # the same id twice
    twice = await refused(
        service().update_list(
            workspace.id,
            created.id,
            OptionListUpdateDto(
                items=[
                    ItemDto(id=ids["Utrecht"], label="A"),
                    ItemDto(id=ids["Utrecht"], label="B"),
                ]
            ),
            testUser,
        )
    )
    assert code_of(twice) == "unknown_item"


async def test_a_save_over_a_newer_revision_is_refused_and_writes_nothing(workspace):
    created = await make_list(workspace)
    await service().update_list(
        workspace.id,
        created.id,
        OptionListUpdateDto(name="First", expected_revision=1),
        testUser,
    )
    error = await refused(
        service().update_list(
            workspace.id,
            created.id,
            OptionListUpdateDto(name="Second", expected_revision=1),
            testUser,
        )
    )
    assert error.status_code == 409 and code_of(error) == "list_changed"
    assert (
        await service().get_list(workspace.id, created.id, testUser)
    ).name == "First"


async def test_csv_round_trips_keeping_ids_and_neutralising_formulas(workspace):
    created = await make_list(
        workspace, items=[("=cmd|'/c calc'!A1", "g"), ("Plain", None), ("+31 6", None)]
    )
    exported = await service().export_csv(workspace.id, created.id, testUser)
    lines = exported.strip().splitlines()
    assert lines[0] == "label,group,id"
    # no cell of the file starts as a formula
    assert lines[1].startswith("'=cmd") or lines[1].startswith("\"'=cmd")
    ids = ids_of(created)
    again = await service().import_csv(
        workspace.id, created.id, exported.encode(), testUser
    )
    assert ids_of(again) == ids  # ids and the neutralised cells read back as they were
    assert again.revision == 2


async def test_csv_import_matches_rows_without_an_id_by_label_and_group(workspace):
    created = await make_list(workspace, items=[("A", "g"), ("B", None)])
    ids = ids_of(created)
    body = "label,group\r\nB,\r\nA,g\r\nNew,\r\n".encode("utf-8-sig")
    result = await service().import_csv(workspace.id, created.id, body, testUser)
    assert [i.label for i in result.items] == ["B", "A", "New"]
    assert result.items[0].id == ids["B"] and result.items[1].id == ids["A"]
    assert result.items[2].id not in ids.values()
    # without a header the columns are label, group, id
    plain = await service().import_csv(workspace.id, created.id, b"Solo,x\n", testUser)
    assert [(i.label, i.group) for i in plain.items] == [("Solo", "x")]


@pytest.mark.parametrize(
    "body,code,status",
    [
        (b"\xff\xfe\x00bad", "invalid_file", 422),
        (
            "label\r\n" + "\r\n".join(f"i{n}" for n in range(text.ITEMS_PER_LIST + 1)),
            "limit_reached",
            422,
        ),
        (b"label,group,id\r\nX,,li" + b"0" * 22 + b"\r\n", "unknown_item", 422),
        (b"label\r\nA\r\nA\r\n", "duplicate_item", 422),
        (b"label\r\n" + b"x" * 1_000_001, "file_too_large", 413),
    ],
)
async def test_a_bad_csv_is_refused(workspace, body, code, status):
    created = await make_list(workspace)
    data = body if isinstance(body, bytes) else body.encode()
    error = await refused(
        service().import_csv(workspace.id, created.id, data, testUser)
    )
    assert code_of(error) == code and error.status_code == status
    assert (
        len((await service().get_list(workspace.id, created.id, testUser)).items) == 5
    )


async def test_a_list_a_form_uses_cannot_be_deleted(workspace):
    created = await make_list(workspace)
    form = await publish(
        workspace,
        [question("city", source={"kind": "list", "list_id": created.id})],
        title="Uses the list",
    )
    summary = (await service().list_lists(workspace.id, testUser))[0]
    assert summary.forms_using == 1
    detail = await service().get_list(workspace.id, created.id, testUser)
    assert [(u.form_id, u.title) for u in detail.used_by] == [
        (form.form_id, "Uses the list")
    ]
    error = await refused(service().delete_list(workspace.id, created.id, testUser))
    assert error.status_code == 409 and code_of(error) == "list_in_use"
    assert error.content["forms"][0]["formId"] == form.form_id
    other = await make_list(workspace, name="Unused")
    await service().delete_list(workspace.id, other.id, testUser)
    assert [s.name for s in await service().list_lists(workspace.id, testUser)] == [
        "Cities"
    ]


async def test_creating_a_list_needs_the_switch_but_stored_lists_stay_editable(
    workspace, monkeypatch
):
    created = await make_list(workspace)
    from backend.config import settings

    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    error = await refused(make_list(workspace, name="New"))
    assert code_of(error) == "option_sources_disabled" and error.status_code == 422
    renamed = await service().update_list(
        workspace.id, created.id, OptionListUpdateDto(name="Renamed"), testUser
    )
    assert renamed.name == "Renamed"
    assert [s.name for s in await service().list_lists(workspace.id, testUser)] == [
        "Renamed"
    ]


# ------------------------------------------------------------------ who may


def _member(name):
    return User(id=str(RecordId()), sub=f"{name}@lists.example")


VIEWER, REVIEWER_USER, PRIVACY, EDITOR, ADMIN = (
    _member(n) for n in ("v", "r", "p", "e", "a")
)
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
            WorkspaceUserDocument(
                workspace_id=workspace.id, user_id=user.id, roles=[role]
            )
        )


def url(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/option-lists{suffix}"


@pytest.mark.parametrize(
    "user,reads,writes",
    [
        (VIEWER, True, False),
        (REVIEWER_USER, True, False),
        (PRIVACY, True, False),  # form structure only: lists are not answers
        (EDITOR, True, True),
        (ADMIN, True, True),
        (testUser1, False, False),  # not a member of this workspace
    ],
)
async def test_reading_needs_form_read_and_writing_form_edit(
    client: AsyncClient, workspace, roles, user, reads, writes
):
    created = await make_list(workspace)
    cookies = _cookies(user)
    got = await client.get(url(workspace), cookies=cookies)
    assert got.status_code == (200 if reads else 403), got.text
    item = await client.get(url(workspace, f"/{created.id}"), cookies=cookies)
    assert item.status_code == (200 if reads else 403)
    exported = await client.get(
        url(workspace, f"/{created.id}/export"), cookies=cookies
    )
    assert exported.status_code == (200 if reads else 403)
    body = {"name": f"By {user.sub}", "items": [{"label": "x"}]}
    post = await client.post(url(workspace), json=body, cookies=cookies)
    assert post.status_code == (201 if writes else 403), post.text
    patched = await client.patch(
        url(workspace, f"/{created.id}"), json={"name": "N"}, cookies=cookies
    )
    assert patched.status_code == (200 if writes else 403)
    imported = await client.post(
        url(workspace, f"/{created.id}/import"),
        content=b"label\r\nA\r\n",
        headers={"Content-Type": "text/csv"},
        cookies=cookies,
    )
    assert imported.status_code == (200 if writes else 403)
    deleted = await client.delete(url(workspace, f"/{created.id}"), cookies=cookies)
    assert deleted.status_code == (204 if writes else 403)


async def test_a_list_of_another_workspace_is_never_found(
    client: AsyncClient, workspace, workspace_1
):
    mine = await make_list(workspace)
    theirs = await make_list(workspace_1, user=testUser1, name="Theirs")
    cookies = _cookies(testUser)
    # through my workspace: their list does not exist
    for method, suffix, extra in (
        ("get", f"/{theirs.id}", {}),
        ("get", f"/{theirs.id}/export", {}),
        ("patch", f"/{theirs.id}", {"json": {"name": "Stolen"}}),
        ("delete", f"/{theirs.id}", {}),
        ("post", f"/{theirs.id}/import", {"content": b"label\r\nA\r\n"}),
    ):
        response = await getattr(client, method)(
            url(workspace, suffix), cookies=cookies, **extra
        )
        assert response.status_code == 404, (method, suffix, response.text)
    # and through theirs, mine does not exist either
    other = f"/api/v1/workspaces/{workspace_1.id}/option-lists/{mine.id}"
    assert (await client.get(other, cookies=_cookies(testUser1))).status_code == 404
    assert (
        await service().get_list(workspace_1.id, theirs.id, testUser1)
    ).name == "Theirs"
    for bad in ("nonsense", "0" * 24, "../" + "a" * 21):
        assert (
            await client.get(url(workspace, f"/{bad}"), cookies=cookies)
        ).status_code in (404, 422)


async def test_an_unauthenticated_call_is_refused(client: AsyncClient, workspace):
    assert (await client.get(url(workspace))).status_code in (401, 403)
