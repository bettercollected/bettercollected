"""The forms group's repositories (forms and their versions, workspace links,
templates, media libraries, workspace consents), Postgres only since 4.1.

These steps ran against the 4.0 Mongo repositories too while both stores
existed (the parity tests of the dual run). The results they agreed on are
pinned in ``tests/fixtures/forms_repositories.json`` (ids and timestamps
aside, as the parity harness compared them); a few are spelled out below as
well. The other groups' data (responder groups, responses and deletion
requests) is read through their repositories as the application does, so
each storage mode composes over its own responses store.

The fixture is written from a run of the 4.0-era repositories whose parity
tests passed (``BC_PIN_FORMS_REPOSITORIES=1``, one process), never
regenerated to make a change pass. Skipped unless DATABASE_URL points at a
*_test database.
"""

import datetime as dt
import json
import os
from enum import Enum
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.models.template import StandardFormTemplate
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.models.standard_form import ParameterValue, StandardForm
from common.models.user import User
from common.records import RecordId
from tests.app.repositories.parity import sessions, strip  # noqa: F401

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
FIXTURE = Path(__file__).parents[2] / "fixtures" / "forms_repositories.json"
PIN = os.getenv("BC_PIN_FORMS_REPOSITORIES") == "1"


def oid(n: int) -> RecordId:
    """A fixed id: the pinned results name workspaces, users and actions."""
    return RecordId(f"{n:024x}")


def _plain(value):
    """``strip``ped results as JSON data (ids and dates left by the raw
    aggregation shapes as strings)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


class Pinned:
    """The results of one test's steps, compared with (or, with
    ``BC_PIN_FORMS_REPOSITORIES=1``, written to) the fixture."""

    def __init__(self, case: str):
        self.case = case
        self.results = {}

    async def step(self, label: str, call, key=None):
        result = await call()
        if isinstance(result, Page):
            value = _plain(
                {
                    "total": result.total,
                    "page": result.page,
                    "pages": result.pages,
                    "items": strip(result.items),
                }
            )
        else:
            value = _plain(strip(result))
        if key is not None:
            value = sorted(value, key=key)
        self.results[f"{len(self.results):02d} {label}"] = value
        return result

    async def steps(self, repo, steps):
        for name, args in steps:
            await self.step(name, lambda: getattr(repo, name)(*args()))

    def check(self):
        pinned = json.loads(FIXTURE.read_text()) if FIXTURE.exists() else {}
        if PIN:
            pinned[self.case] = self.results
            FIXTURE.write_text(json.dumps(pinned, indent=1, sort_keys=True) + "\n")
            return
        expected = pinned[self.case]
        assert list(self.results) == list(expected)
        for label, value in self.results.items():
            assert value == expected[label], label


async def raises_status(status, call):
    with pytest.raises(HTTPException) as raised:
        await call()
    assert raised.value.status_code == status


def form(form_id, title, minutes, **extra):
    return FormDocument(
        id=RecordId(),
        form_id=form_id,
        title=title,
        builder_version="v2",
        created_at=T0 + dt.timedelta(minutes=minutes),
        **extra,
    )


def workspace_form(workspace_id, form_id, user_id, minutes, **settings):
    return WorkspaceFormDocument(
        id=RecordId(),
        workspace_id=workspace_id,
        form_id=form_id,
        user_id=user_id,
        settings=WorkspaceFormSettings(**settings),
        created_at=T0 + dt.timedelta(minutes=minutes),
    )


def version(document: FormDocument, number: int):
    v = FormVersionsDocument(**document.model_dump(mode="json"), version=number)
    v.id = RecordId()
    return v


def form_repos(sessions):
    groups = container.responder_groups_repository()
    forms = PostgresFormRepository(sessions, groups, container.form_response_repo())
    return groups, forms, PostgresWorkspaceFormRepository(sessions, groups)


async def respond(form_id, response_id, workspace_id=None, request=False):
    """A response (and its deletion request) through the responses group's
    repository, as the application stores them."""
    responses = container.form_response_repo()
    saved = await responses.save(
        FormResponseDocument(
            form_id=form_id,
            response_id=response_id,
            answers={},
            workspace_id=workspace_id,
        )
    )
    if request:
        await responses.add_deletion_request(saved, response_id)
    return saved


def by_form_id(row):
    return row["form_id"]


# --------------------------------------------------------------------------- forms
async def test_form_listings_search_and_versions(sessions):
    ws, elsewhere = oid(1), oid(2)
    groups, forms, links = form_repos(sessions)
    pinned = Pinned("form_listings_search_and_versions")
    documents = (
        form("f1", "Alpha survey", 1, description="first"),
        form("f2", "Beta poll", 2, description="alpha-ish"),
        form("f3", "Gamma quiz", 3),
    )
    for document in documents:
        await forms.save_form(document)
    for link in (
        workspace_form(ws, "f1", "u1", 1, custom_url="alpha", provider="self"),
        workspace_form(ws, "f2", "u2", 2, private=True),
        workspace_form(ws, "f3", "u1", 3),
        workspace_form(oid(3), "f1", "u9", 4),  # imported elsewhere too
    ):
        await links.save(link)
    for number in (1, 2):
        await forms.save_form_version(version(documents[0], number))
    group = await groups.create_group(ws, "Corp", regex=".*@corp.com")
    await groups.add_group_to_form("f1", group.id)
    # f1 is linked to another workspace too: only the responses collected
    # here count (#768); one stored before workspace_id existed is
    # ambiguous and counts nowhere. f3 is this workspace's only: its
    # unstamped response is its own.
    await respond("f1", "r1", ws, request=True)
    await respond("f1", "r2", ws)
    await respond("f1", "r3", elsewhere, request=True)
    await respond("f1", "r4")
    await respond("f3", "r5")

    ids = ["f1", "f2", "f3", "missing"]
    default_sort = SortRequest()
    by_title = SortRequest(sort_by="title", sort_order=SortOrder.ASCENDING)
    await pinned.steps(
        forms,
        [
            ("get_forms_in_workspace", lambda: (ws, ids, True, default_sort)),
            ("get_forms_in_workspace", lambda: (ws, ids, False, default_sort)),
            ("get_forms_in_workspace", lambda: (ws, ids, True, by_title)),
            ("get_forms_in_workspace", lambda: (ws, ["f1"], True)),
            ("get_published_forms_in_workspace", lambda: (ws, ids, default_sort)),
            ("get_published_forms_in_workspace", lambda: (ws, ids, default_sort, True)),
            ("search_form_in_workspace", lambda: (ws, ids, "alp")),
            ("search_form_in_workspace", lambda: (ws, ids, "ALPHA", True)),
            ("search_form_in_workspace", lambda: (ws, ids, "nothing")),
            ("get_forms_by_form_ids", lambda: (["f1", "f3"],)),
            ("get_form_document_by_id", lambda: ("f2",)),
            ("get_form_by_id", lambda: ("f2",)),
            ("get_latest_version_of_form", lambda: ("f1",)),
            ("get_latest_version_of_form", lambda: ("f2",)),
            ("get_form_by_by_version", lambda: ("f1", FormVersion.latest)),
            ("get_form_by_by_version", lambda: ("f1", 1)),
            ("get_form_by_by_version", lambda: ("f1", 9)),
        ],
    )
    listed = await forms.get_forms_in_workspace(ws, ids, True, default_sort)
    f1 = next(f for f in listed if f["form_id"] == "f1")
    assert (f1["responses"], f1["deletion_requests"], f1["is_published"]) == (
        2,
        1,
        True,
    )
    f3 = next(f for f in listed if f["form_id"] == "f3")
    assert (f3["responses"], f3["deletion_requests"]) == (1, 0)
    assert [str(g["_id"]) for g in f1["groups"]] == [str(group.id)]
    assert f1["settings"]["custom_url"] == "alpha" and f1["imported_by"] == "u1"

    with set_page(Page), set_params(Params(page=1, size=2)):
        page = await pinned.step(
            "paginate_forms_in_workspace",
            lambda: forms.paginate_forms_in_workspace(ws, ids, True, default_sort),
        )
        assert (page.total, page.page, page.pages) == (3, 1, 2)
        page = await pinned.step(
            "paginate_published_forms_in_workspace",
            lambda: forms.paginate_published_forms_in_workspace(ws, ids, default_sort),
        )
        assert page.total == 1

    # writes
    updated = StandardForm(
        form_id="f2", title="Beta poll v2", fields=[], hidden_fields=None
    )
    await pinned.steps(
        forms,
        [
            ("update_form", lambda: ("f2", updated)),
            ("get_form_document_by_id", lambda: ("f2",)),
            ("delete_versions_by_imported_form_id", lambda: ("nothing",)),
            ("delete_form", lambda: ("f3",)),
            ("get_forms_by_form_ids", lambda: (["f1", "f2", "f3"],)),
            ("delete_forms", lambda: (["f2"],)),
            ("get_forms_by_form_ids", lambda: (["f1", "f2", "f3"],)),
        ],
    )
    await raises_status(404, lambda: forms.delete_form("f3"))
    created = StandardForm(form_id="f9", title="Nine", fields=[])
    await pinned.step("create_form", lambda: forms.create_form(created))
    await pinned.step(
        "publish_form",
        lambda: _publish(forms, "f9", 1),
    )
    await pinned.step(
        "get_latest_version_of_form", lambda: forms.get_latest_version_of_form("f9")
    )
    pinned.check()


async def _publish(forms, form_id, number):
    return await forms.publish_form(await forms.get_form_document_by_id(form_id), number)


async def test_a_form_linked_twice_to_a_workspace_counts_once(sessions):
    """One link per workspace and form: saving the link again keeps one, and
    the form's unstamped response counts in that workspace (#768)."""
    ws = oid(1)
    _, forms, links = form_repos(sessions)
    document = form("dup", "Duplicated link", 1)
    await forms.save_form(document)
    await forms.save_form_version(version(document, 1))
    await links.save_workspace_form(ws, "dup", "u1", WorkspaceFormSettings())
    await links.save_workspace_form(ws, "dup", "u1", WorkspaceFormSettings())
    assert len(await links.get_workspace_forms_form_ids(["dup"])) == 1
    await respond("dup", "d1", ws)
    await respond("dup", "d2", None, request=True)

    def counts(rows):
        return {(r["form_id"], r["responses"], r["deletion_requests"]) for r in rows}

    expected = {("dup", 2, 1)}
    assert counts(await forms.get_forms_in_workspace(ws, ["dup"], True)) == expected
    assert counts(await forms.get_published_forms_in_workspace(ws, ["dup"])) == expected


# ----------------------------------------------------------------- workspace forms
async def test_workspace_form_visibility(sessions):
    ws, other = oid(1), oid(2)
    groups, _, links = form_repos(sessions)
    pinned = Pinned("workspace_form_visibility")
    owner = User(id=str(oid(10)), sub="owner@example.com")
    member = User(id=str(oid(11)), sub="member@example.com")
    corp = User(id=str(oid(12)), sub="dev@corp.com")
    for link in (
        workspace_form(ws, "pub", "u1", 1, custom_url="public-slug", provider="self"),
        workspace_form(ws, "priv", "u1", 2, private=True),
        workspace_form(ws, "hidden", owner.id, 3, hidden=True),
        workspace_form(ws, "members", "u1", 4, private=True),
        workspace_form(ws, "corp", "u1", 5, private=True, pinned=True),
        workspace_form(
            ws, "closed", "u1", 6, form_close_date="2020-01-01T00:00:00+00:00"
        ),
        workspace_form(ws, "open", "u1", 7, form_close_date=""),
        workspace_form(ws, "imported", "u1", 8, provider="google"),
        workspace_form(other, "elsewhere", "u1", 9),
        workspace_form(ws, "glob", "u1", 10, private=True),
    ):
        await links.save(link)
    members = await groups.create_group(ws, "Members")
    await groups.add_emails_to_group(members.id, ["member@example.com"])
    await groups.add_group_to_form("members", members.id)
    corp_group = await groups.create_group(ws, "Corp", regex=".*@corp.com")
    await groups.add_group_to_form("corp", corp_group.id)
    # a glob typed where a regex was expected (seen in production): it must
    # admit nobody and never break the listing for the workspace
    glob_group = await groups.create_group(ws, "Glob", regex="*@corp.com")
    await groups.add_group_to_form("glob", glob_group.id)

    for label, kwargs in (
        ("all", {}),
        ("owner", dict(user=owner)),
        ("not admin", dict(is_not_admin=True)),
        ("member", dict(is_not_admin=True, user=member)),
        ("corp", dict(is_not_admin=True, user=corp)),
        ("owner not admin", dict(is_not_admin=True, user=owner)),
        ("pinned", dict(pinned_only=True)),
        ("form id", dict(form_id="priv")),
        ("slug", dict(form_id_or_slug="public-slug")),
        ("id as slug", dict(form_id_or_slug="priv")),
        ("open only", dict(filter_closed=True)),
        ("ids only", dict(is_not_admin=True, user=member, id_only=True)),
    ):
        await pinned.step(
            f"get_workspace_forms_in_workspace {label}",
            lambda: links.get_workspace_forms_in_workspace(ws, **kwargs),
            key=str,
        )
    await pinned.step(
        "get_form_ids_in_workspace member",
        lambda: links.get_form_ids_in_workspace(ws, True, member),
        key=str,
    )
    await pinned.step(
        "get_form_ids_in_workspace open",
        lambda: links.get_form_ids_in_workspace(ws, filter_closed=True),
        key=str,
    )

    # the composed responder-group check admits the right people
    async def ids(user):
        return {
            wf["form_id"]
            for wf in await links.get_workspace_forms_in_workspace(ws, True, user)
        }

    assert await ids(None) == {"pub", "closed", "open", "imported"}
    assert await ids(member) == {"pub", "closed", "open", "imported", "members"}
    assert await ids(corp) == {"pub", "closed", "open", "imported", "corp"}

    await pinned.steps(
        links,
        [
            ("find_workspace_form", lambda: (ws, "pub")),
            ("find_workspace_form", lambda: (ws, "nope")),
            ("get_workspace_form_in_workspace", lambda: (ws, "public-slug")),
            ("get_workspace_form_in_workspace", lambda: (ws, "priv", False)),
            (
                "get_workspace_form_with_custom_slug_form_id",
                lambda: (ws, "public-slug"),
            ),
            ("get_workspace_ids_for_form_id", lambda: ("pub",)),
            ("get_form_ids_imported_by_user", lambda: (ws, "u1")),
            ("check_if_form_exists_in_workspace", lambda: (ws, "pub")),
            ("check_if_form_exists_in_workspace", lambda: (other, "pub")),
            ("check_is_form_imported_in_other_workspace", lambda: (ws, "pub")),
            ("list_in_workspace", lambda: (ws,)),
        ],
    )
    imported = sorted(
        await links.get_form_ids_in_workspaces_and_imported_by_user([ws], owner)
    )
    assert "pub" not in imported and "imported" in imported  # provider != "self"
    # case-duplicate accounts: every provider, distinct forms, owned or imported
    for workspaces, user_id, expected in (
        ([ws], "nobody", 9),
        ([], "u1", 9),
        ([], owner.id, 1),
        ([other], owner.id, 2),
        ([], "nobody", 0),
    ):
        assert await links.count_forms_of_account(workspaces, user_id) == expected
    pinned.results[f"{len(pinned.results):02d} imported by user"] = imported
    await raises_status(
        409,
        lambda: links.check_is_form_imported_in_other_workspace(ws, "elsewhere"),
    )
    settings = WorkspaceFormSettings(private=True, custom_url="renamed")
    await pinned.steps(
        links,
        [
            ("save_workspace_form", lambda: (ws, "pub", "u1", settings)),
            ("find_workspace_form", lambda: (ws, "pub")),
            ("delete_form_in_workspace", lambda: (ws, "closed")),
            ("delete_forms", lambda: (["open"],)),
            ("get_workspace_forms_form_ids", lambda: (["pub", "closed", "open"],)),
        ],
    )
    await raises_status(404, lambda: links.delete_form_in_workspace(ws, "closed"))
    missing = str(RecordId())
    await raises_status(
        404, lambda: links.update(missing, workspace_form(ws, "x", "u", 0))
    )
    pinned.check()


# --------------------------------------------------------------------- templates
async def test_templates(sessions):
    ws, origin_ws, gone_ws = oid(1), oid(2), oid(3)
    workspaces = PostgresWorkspaceRepository(
        sessions, PostgresActionRepository(sessions, None)
    )
    await workspaces.save(
        WorkspaceDocument(id=origin_ws, title="Origin", workspace_name="origin-ws")
    )
    templates = PostgresFormTemplateRepository(sessions, workspaces)
    pinned = Pinned("templates")

    def template(title, minutes, **extra):
        return FormTemplateDocument(
            id=oid(100 + minutes),
            title=title,
            workspace_id=ws,
            created_at=T0 + dt.timedelta(minutes=minutes),
            **extra,
        )

    docs = (
        template("plain", 1),
        template("v2", 2, builder_version="v2"),
        template("from origin", 3, imported_from=origin_ws),
        template("from nowhere", 4, imported_from=gone_ws),
        template("public", 5, settings={"is_public": True}),
    )
    for doc in docs:
        await templates.save(doc)
    await pinned.steps(
        templates,
        [
            ("get_templates_with_creator", lambda: (None, ws)),
            ("get_templates_with_creator", lambda: (True, ws)),
            ("get_templates_with_creator", lambda: (None, ws, docs[2].id)),
            ("get_templates_with_creator", lambda: (None, ws, None, True)),
            ("get_templates_with_creator", lambda: (None, None)),
            ("get_template_by_id", lambda: (docs[0].id,)),
            ("get_template_by_id", lambda: (RecordId(),)),
            ("get_template_by_workspace_id_n_template_id", lambda: (ws, docs[1].id)),
            ("get_template_by_id_with_creator", lambda: (ws, docs[2].id)),
            ("get_v2_template_by_title", lambda: ("v2",)),
            ("get_v2_template_by_title", lambda: ("plain",)),  # not v2
            ("get_v2_template_by_title", lambda: ("missing",)),
        ],
    )
    listed = await templates.get_templates_with_creator(workspace_id=ws)
    by_title = {t["title"]: t for t in listed}
    assert by_title["from origin"]["imported_from"] == "Origin"
    assert str(by_title["from origin"]["id"]) == str(docs[2].id)
    assert "imported_from" not in by_title["from nowhere"]
    await raises_status(
        404, lambda: templates.get_template_by_id_with_creator(ws, RecordId())
    )
    body = StandardFormTemplate(title="Fresh", description="d", fields=[])
    user = User(id=str(oid(10)), sub="u@example.com")
    await pinned.step(
        "create_new_template", lambda: templates.create_new_template(ws, body, user)
    )
    await pinned.step(
        "import_template_to_workspace",
        lambda: templates.import_template_to_workspace(gone_ws, docs[0].id),
    )
    body.title = "Renamed"
    await pinned.steps(
        templates,
        [
            ("update_template", lambda: (docs[0].id, body)),
            ("get_template_by_id", lambda: (docs[0].id,)),
            ("delete_template", lambda: (docs[1].id,)),
            ("get_template_by_id", lambda: (docs[1].id,)),
        ],
    )
    await raises_status(404, lambda: templates.delete_template(docs[1].id))
    pinned.check()


# ---------------------------------------------------------- media library, consent
async def test_media_library(sessions):
    ws = str(oid(1))
    media = PostgresMediaLibraryRepository(sessions)
    added = [
        await media.add_media_in_workspace_library(
            ws, f"http://x/{n}", "IMAGE", n, f"k/{n}"
        )
        for n in ("Logo", "banner", "logo-dark")
    ]
    assert [m.media_name for m in added] == ["Logo", "banner", "logo-dark"]
    assert len({m.media_id for m in added}) == 3

    async def names(query):
        found = await media.get_media_library_by_worksapce_id(ws, query)
        return [m.media_name for m in found]

    # newest first; the search is case-insensitive
    assert await names(None) == ["logo-dark", "banner", "Logo"]
    assert await names("logo") == ["logo-dark", "Logo"]
    assert await names("zzz") == []
    assert await media.get_media_library_by_worksapce_id("other", None) == []
    media_id = added[1].media_id
    single = await media.get_single_media_from_workspace_library(ws, media_id)
    assert (single.media_name, single.media_url, single.media_type) == (
        "banner",
        "http://x/banner",
        "IMAGE",
    )
    assert await media.delete_media_from_library(ws, media_id) == media_id
    assert await media.get_single_media_from_workspace_library(ws, media_id) is None
    assert await names(None) == ["logo-dark", "Logo"]


async def test_workspace_consent(sessions):
    ws = oid(1)
    consents = PostgresWorkspaceConsentRepo(sessions)
    consent = ConsentCamelModel(
        title="Newsletter",
        type="checkbox",
        category="purpose_of_the_form",
        required=False,
    )
    assert await consents.get_workspace_consents(ws) == []
    created = await consents.create_workspace_consent(ws, consent)
    assert (created.title, str(created.workspace_id)) == ("Newsletter", str(ws))
    stored = await consents.get_workspace_consents(ws)
    assert [(c.title, c.type, c.category, c.required) for c in stored] == [
        ("Newsletter", "checkbox", "purpose_of_the_form", False)
    ]
    assert await consents.get_workspace_consents(oid(2)) == []


# ------------------------------------------------------------------ action state
async def test_action_parameters_and_secrets(sessions):
    """The Sheets re-consent markers (services/sheets_reconsent.py): one
    action's parameters change, nothing else does (not ``updated_at``), and
    a marker is claimed once."""
    _, forms, _ = form_repos(sessions)
    a1, a2 = str(oid(21)), str(oid(22))
    await forms.save_form(
        form(
            "p1",
            "With",
            1,
            parameters={
                a1: [ParameterValue(name="Title", value="Sheet")],
                a2: [ParameterValue(name="Url", value="u")],
            },
            secrets={a1: [ParameterValue(name="Credentials", value="c")]},
        )
    )
    await forms.save_form(form("p2", "Without", 2))
    before = (await forms.get_form_document_by_id("p1")).updated_at

    async def update(*args):
        return await forms.update_action_parameters(*args)

    assert await update("p1", a1, {"needs_reconsent": "true"}) is True
    assert await update("p1", a1, {"needs_reconsent": "true"}) is False  # no change
    assert await update("p1", a1, None, "skipped") is True
    assert await update("p1", a1, None, "skipped") is True
    assert await update("p1", a1, {"m": "t"}, None, "m") is True
    assert await update("p1", a1, {"m": "t2"}, None, "m") is False  # claimed once
    assert await update("p1", a1, None, None, None, ["m"]) is True
    # no parameters at all yet, and an unknown form
    assert await update("p2", a1, {"needs_reconsent": "true"}) is True
    assert await update("nope", a1, {"x": "y"}) is False

    with_secrets = await forms.get_forms_with_action_secrets([a1])
    assert [f.form_id for f in with_secrets] == ["p1"]
    assert await forms.get_forms_with_action_secrets([a2]) == []
    assert await forms.get_forms_with_action_secrets([]) == []

    stored = await forms.get_form_document_by_id("p1")
    assert {p.name: p.value for p in stored.parameters[a1]} == {
        "Title": "Sheet",
        "needs_reconsent": "true",
        "skipped": "2",
    }
    assert [p.value for p in stored.parameters[a2]] == ["u"]
    assert stored.updated_at == before
    bare = await forms.get_form_document_by_id("p2")
    assert [(p.name, p.value) for p in bare.parameters[a1]] == [
        ("needs_reconsent", "true")
    ]


async def test_replace_action_credential(sessions):
    """A new Sheets grant (services/sheets_grant_revocation.py): one write
    stores the credential and drops the re-consent markers; the draft's
    previous ciphertext is returned; published versions' copies are replaced;
    other actions, other secrets and ``updated_at`` stay as they were."""
    _, forms, _ = form_repos(sessions)
    a1, a2 = str(oid(21)), str(oid(22))
    draft = form(
        "p1",
        "With",
        1,
        parameters={
            a1: [
                ParameterValue(name="Title", value="Sheet"),
                ParameterValue(name="needs_reconsent", value="true"),
                ParameterValue(name="reconsent_skipped_runs", value="3"),
                ParameterValue(name="reconsent_mailed_at", value="t"),
            ],
            a2: [ParameterValue(name="needs_reconsent", value="true")],
        },
        secrets={
            a1: [
                ParameterValue(name="Credentials", value="old"),
                ParameterValue(name="Other", value="kept"),
            ],
            a2: [ParameterValue(name="Credentials", value="other-action")],
        },
    )
    await forms.save_form(draft)
    await forms.save_form(form("p2", "Bare", 2))
    for number in (1, 2):
        await forms.save_form_version(version(draft, number))
    before = (await forms.get_form_document_by_id("p1")).updated_at
    markers = ["needs_reconsent", "reconsent_skipped_runs", "reconsent_mailed_at"]

    replace = forms.replace_action_credential
    assert await replace("p1", a1, "new", markers) == {
        "stored": True,
        "previous": "old",
    }
    # again: the previous one is now the new one, nothing left to drop
    assert await replace("p1", a1, "new", markers) == {
        "stored": True,
        "previous": "new",
    }
    # no secrets or parameters at all yet, and an unknown form
    assert await replace("p2", a1, "first", markers) == {
        "stored": True,
        "previous": None,
    }
    assert await replace("nope", a1, "x", markers) == {
        "stored": False,
        "previous": None,
    }

    stored = await forms.get_form_document_by_id("p1")
    assert {p.name: p.value for p in stored.parameters[a1]} == {"Title": "Sheet"}
    assert {s.name: s.value for s in stored.secrets[a1]} == {
        "Credentials": "new",
        "Other": "kept",
    }
    assert [p.value for p in stored.parameters[a2]] == ["true"]
    assert [s.value for s in stored.secrets[a2]] == ["other-action"]
    assert stored.updated_at == before
    bare = await forms.get_form_document_by_id("p2")
    assert [(s.name, s.value) for s in bare.secrets[a1]] == [("Credentials", "first")]
    published_versions = await forms.get_versions_of_form("p1")
    assert [v.version for v in published_versions] == [1, 2]
    for published in published_versions:
        assert {s.name: s.value for s in published.secrets[a1]} == {
            "Credentials": "new",
            "Other": "kept",
        }
        assert [s.value for s in published.secrets[a2]] == ["other-action"]
