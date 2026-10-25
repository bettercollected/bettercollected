"""The Postgres twins of the forms-group repositories behave like the Mongo originals.

Cross-group data (responder groups, responses, the workspaces templates were
imported from) lives in Mongo for both sides here — the twins compose over the
other groups' repositories, exactly as in a staged cutover.
Skipped unless DATABASE_URL points at a *_test database.
"""

import datetime as dt

import pytest
from beanie import PydanticObjectId
from fastapi_pagination import Page, Params
from fastapi_pagination.api import set_page, set_params

from backend.app.container import container
from backend.app.handlers.database import ensure_workspace_form_unique_index
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.consent import ConsentCamelModel
from backend.app.models.enum.FormVersion import FormVersion
from backend.app.models.filter_queries.sort import SortOrder, SortRequest
from backend.app.models.template import StandardFormTemplate
from backend.app.models.workspace import WorkspaceFormSettings
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.media_library_repository import MediaLibraryRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresFormTemplateRepository,
    PostgresMediaLibraryRepository,
    PostgresWorkspaceConsentRepo,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.repositories.template import FormTemplateRepository
from backend.app.repositories.workspace_consent_repo import WorkspaceConsentRepo
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.template import FormTemplateDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.models.standard_form import ParameterValue, StandardForm
from common.models.user import User
from tests.app.repositories.test_identity_parity import both_raise
from tests.app.repositories.parity import parity, strip

T0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def form(form_id, title, minutes, **extra):
    return FormDocument(
        id=PydanticObjectId(),
        form_id=form_id,
        title=title,
        builder_version="v2",
        created_at=T0 + dt.timedelta(minutes=minutes),
        **extra,
    )


def workspace_form(workspace_id, form_id, user_id, minutes, **settings):
    return WorkspaceFormDocument(
        id=PydanticObjectId(),
        workspace_id=workspace_id,
        form_id=form_id,
        user_id=user_id,
        settings=WorkspaceFormSettings(**settings),
        created_at=T0 + dt.timedelta(minutes=minutes),
    )


def version(document: FormDocument, number: int):
    v = FormVersionsDocument(**document.model_dump(mode="json"), version=number)
    v.id = PydanticObjectId()
    return v


async def seed_both(pairs, method, *documents):
    for repo in pairs:
        for document in documents:
            await getattr(repo, method)(document)


def by_form_id(rows):
    return sorted(strip(rows), key=lambda r: r["form_id"])


async def same_rows(mongo_call, postgres_call):
    assert by_form_id(await mongo_call()) == by_form_id(await postgres_call())


# --------------------------------------------------------------------------- forms
async def test_form_listings_search_and_versions(sessions):
    ws = PydanticObjectId()
    groups, responses = ResponderGroupsRepository(), FormResponseRepository(
        crypto=container.crypto()
    )
    mongo = FormRepository()
    postgres = PostgresFormRepository(sessions, groups, responses)
    forms = (
        form("f1", "Alpha survey", 1, description="first"),
        form("f2", "Beta poll", 2, description="alpha-ish"),
        form("f3", "Gamma quiz", 3),
    )
    await seed_both((mongo, postgres), "save_form", *forms)
    mongo_wf, postgres_wf = (
        WorkspaceFormRepository(),
        PostgresWorkspaceFormRepository(sessions, groups),
    )
    await seed_both(
        (mongo_wf, postgres_wf),
        "save",
        workspace_form(ws, "f1", "u1", 1, custom_url="alpha", provider="self"),
        workspace_form(ws, "f2", "u2", 2, private=True),
        workspace_form(ws, "f3", "u1", 3),
        workspace_form(PydanticObjectId(), "f1", "u9", 4),  # imported elsewhere too
    )
    await seed_both(
        (mongo, postgres),
        "save_form_version",
        version(forms[0], 1),
        version(forms[0], 2),
    )
    # cross-group data, in Mongo only
    group = await groups.create_group(ws, "Corp", regex=".*@corp.com")
    await groups.add_group_to_form("f1", group.id)
    # f1 is linked to another workspace too: only the responses collected
    # here count (#768); one stored before workspace_id existed is
    # ambiguous and counts nowhere. f3 is this workspace's only: its
    # unstamped response is its own.
    elsewhere = PydanticObjectId()
    for response_id, workspace_id in (("r1", ws), ("r2", ws), ("r3", elsewhere)):
        await FormResponseDocument(
            form_id="f1", response_id=response_id, answers={}, workspace_id=workspace_id
        ).save()
    await FormResponseDocument(form_id="f1", response_id="r4", answers={}).save()
    await FormResponseDocument(form_id="f3", response_id="r5", answers={}).save()
    await FormResponseDeletionRequest(
        form_id="f1", response_id="r1", workspace_id=ws
    ).save()
    await FormResponseDeletionRequest(
        form_id="f1", response_id="r3", workspace_id=elsewhere
    ).save()

    ids = ["f1", "f2", "f3", "missing"]
    default_sort = SortRequest()
    by_title = SortRequest(sort_by="title", sort_order=SortOrder.ASCENDING)
    await parity(
        mongo,
        postgres,
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
    listed = await postgres.get_forms_in_workspace(ws, ids, True, default_sort)
    f1 = next(f for f in listed if f["form_id"] == "f1")
    assert (f1["responses"], f1["deletion_requests"], f1["is_published"]) == (
        2,
        1,
        True,
    )
    f3 = next(f for f in listed if f["form_id"] == "f3")
    assert (f3["responses"], f3["deletion_requests"]) == (1, 0)
    assert [g["_id"] for g in f1["groups"]] == [group.id]
    assert f1["settings"]["custom_url"] == "alpha" and f1["imported_by"] == "u1"

    with set_page(Page), set_params(Params(page=1, size=2)):
        m_page = await mongo.paginate_forms_in_workspace(ws, ids, True, default_sort)
        p_page = await postgres.paginate_forms_in_workspace(ws, ids, True, default_sort)
        assert (m_page.total, m_page.page, m_page.pages) == (
            p_page.total,
            p_page.page,
            p_page.pages,
        )
        assert strip(m_page.items) == strip(p_page.items)
        m_page = await mongo.paginate_published_forms_in_workspace(
            ws, ids, default_sort
        )
        p_page = await postgres.paginate_published_forms_in_workspace(
            ws, ids, default_sort
        )
        assert m_page.total == p_page.total == 1
        assert strip(m_page.items) == strip(p_page.items)

    # writes
    updated = StandardForm(
        form_id="f2", title="Beta poll v2", fields=[], hidden_fields=None
    )
    await parity(
        mongo,
        postgres,
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
    await both_raise(
        HTTPException,
        lambda: mongo.delete_form("f3"),
        lambda: postgres.delete_form("f3"),
    )
    created = StandardForm(form_id="f9", title="Nine", fields=[])
    assert strip(await mongo.create_form(created)) == strip(
        await postgres.create_form(created)
    )
    published = [
        strip(await repo.publish_form(await repo.get_form_document_by_id("f9"), 1))
        for repo in (mongo, postgres)
    ]
    assert published[0] == published[1]
    assert strip(await mongo.get_latest_version_of_form("f9")) == strip(
        await postgres.get_latest_version_of_form("f9")
    )


async def test_listing_counts_distinct_workspaces_not_link_rows(sessions):
    """Mongo holds the form's link to ``ws`` twice; Postgres once (one link
    per workspace and form). Either way the form is linked to ``ws`` only, so
    its unstamped response counts there, in both stores."""
    ws = PydanticObjectId()
    groups, responses = ResponderGroupsRepository(), FormResponseRepository(
        crypto=container.crypto()
    )
    mongo = FormRepository()
    postgres = PostgresFormRepository(sessions, groups, responses)
    document = form("dup", "Duplicated link", 1)
    await seed_both((mongo, postgres), "save_form", document)
    await seed_both((mongo, postgres), "save_form_version", version(document, 1))
    link = workspace_form(ws, "dup", "u1", 1)
    await seed_both(
        (WorkspaceFormRepository(), PostgresWorkspaceFormRepository(sessions, groups)),
        "save",
        link,
    )
    # the Mongo duplicate: a database holding one has no unique link index
    # (startup skips it and logs an error), so drop it for this test
    links = WorkspaceFormDocument.get_pymongo_collection()
    await links.drop_index("uq_workspace_forms_workspace_form")
    try:
        await workspace_form(ws, "dup", "u1", 2).insert()
        await _assert_counted_once(ws, mongo, postgres)
    finally:
        await links.delete_many({"form_id": "dup"})
        assert await ensure_workspace_form_unique_index(links.database)


async def _assert_counted_once(ws, mongo, postgres):
    for response_id, workspace_id in (("d1", ws), ("d2", None)):
        await FormResponseDocument(
            form_id="dup",
            response_id=response_id,
            answers={},
            workspace_id=workspace_id,
        ).save()
    await FormResponseDeletionRequest(form_id="dup", response_id="d2").save()

    def counts(rows):
        return {(r["form_id"], r["responses"], r["deletion_requests"]) for r in rows}

    expected = {("dup", 2, 1)}
    for listing, args in (
        ("get_forms_in_workspace", (ws, ["dup"], True)),
        ("get_published_forms_in_workspace", (ws, ["dup"])),
    ):
        assert counts(await getattr(mongo, listing)(*args)) == expected, listing
        assert counts(await getattr(postgres, listing)(*args)) == expected, listing


# ----------------------------------------------------------------- workspace forms
async def test_workspace_form_visibility(sessions):
    ws, other = PydanticObjectId(), PydanticObjectId()
    groups = ResponderGroupsRepository()
    mongo, postgres = WorkspaceFormRepository(), PostgresWorkspaceFormRepository(
        sessions, groups
    )
    owner = User(id=str(PydanticObjectId()), sub="owner@example.com")
    member = User(id=str(PydanticObjectId()), sub="member@example.com")
    corp = User(id=str(PydanticObjectId()), sub="dev@corp.com")
    await seed_both(
        (mongo, postgres),
        "save",
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
    )
    members = await groups.create_group(ws, "Members")
    await groups.add_emails_to_group(members.id, ["member@example.com"])
    await groups.add_group_to_form("members", members.id)
    corp_group = await groups.create_group(ws, "Corp", regex=".*@corp.com")
    await groups.add_group_to_form("corp", corp_group.id)
    # a glob typed where a regex was expected (seen in production): it must
    # admit nobody and never break the listing for the workspace
    glob_group = await groups.create_group(ws, "Glob", regex="*@corp.com")
    await groups.add_group_to_form("glob", glob_group.id)

    def listing(**kwargs):
        return lambda repo: repo.get_workspace_forms_in_workspace(ws, **kwargs)

    for call in [
        listing(),
        listing(user=owner),
        listing(is_not_admin=True),
        listing(is_not_admin=True, user=member),
        listing(is_not_admin=True, user=corp),
        listing(is_not_admin=True, user=owner),
        listing(pinned_only=True),
        listing(form_id="priv"),
        listing(form_id_or_slug="public-slug"),
        listing(form_id_or_slug="priv"),
        listing(filter_closed=True),
        listing(is_not_admin=True, user=member, id_only=True),
        lambda repo: repo.get_form_ids_in_workspace(ws, True, member),
        lambda repo: repo.get_form_ids_in_workspace(ws, filter_closed=True),
    ]:
        m, p = await call(mongo), await call(postgres)
        assert sorted(strip(m), key=str) == sorted(strip(p), key=str), call

    # the composed responder-group check admits the right people
    async def ids(user):
        return {
            wf["form_id"]
            for wf in await postgres.get_workspace_forms_in_workspace(ws, True, user)
        }

    assert await ids(None) == {"pub", "closed", "open", "imported"}
    assert await ids(member) == {"pub", "closed", "open", "imported", "members"}
    assert await ids(corp) == {"pub", "closed", "open", "imported", "corp"}

    await parity(
        mongo,
        postgres,
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
        ],
    )
    assert strip(await mongo.list_in_workspace(ws)) == strip(
        await postgres.list_in_workspace(ws)
    )
    imported = [
        sorted(await repo.get_form_ids_in_workspaces_and_imported_by_user([ws], owner))
        for repo in (mongo, postgres)
    ]
    assert imported[0] == imported[1]
    assert "pub" not in imported[0] and "imported" in imported[0]  # provider != "self"
    await both_raise(
        HTTPException,
        lambda: mongo.check_is_form_imported_in_other_workspace(ws, "elsewhere"),
        lambda: postgres.check_is_form_imported_in_other_workspace(ws, "elsewhere"),
    )
    settings = WorkspaceFormSettings(private=True, custom_url="renamed")
    await parity(
        mongo,
        postgres,
        [
            ("save_workspace_form", lambda: (ws, "pub", "u1", settings)),
            ("find_workspace_form", lambda: (ws, "pub")),
            ("delete_form_in_workspace", lambda: (ws, "closed")),
            ("delete_forms", lambda: (["open"],)),
            ("get_workspace_forms_form_ids", lambda: (["pub", "closed", "open"],)),
        ],
    )
    await both_raise(
        HTTPException,
        lambda: mongo.delete_form_in_workspace(ws, "closed"),
        lambda: postgres.delete_form_in_workspace(ws, "closed"),
    )
    missing = str(PydanticObjectId())
    await both_raise(
        HTTPException,
        lambda: mongo.update(missing, workspace_form(ws, "x", "u", 0)),
        lambda: postgres.update(missing, workspace_form(ws, "x", "u", 0)),
    )


# --------------------------------------------------------------------- templates
async def test_templates(sessions):
    ws, origin_ws, gone_ws = PydanticObjectId(), PydanticObjectId(), PydanticObjectId()
    workspaces = WorkspaceRepository()
    await workspaces.save(
        WorkspaceDocument(id=origin_ws, title="Origin", workspace_name="origin-ws")
    )
    mongo, postgres = FormTemplateRepository(workspaces), PostgresFormTemplateRepository(
        sessions, workspaces
    )

    def template(title, minutes, **extra):
        return FormTemplateDocument(
            id=PydanticObjectId(),
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
    await seed_both((mongo, postgres), "save", *docs)
    await parity(
        mongo,
        postgres,
        [
            ("get_templates_with_creator", lambda: (None, ws)),
            ("get_templates_with_creator", lambda: (True, ws)),
            ("get_templates_with_creator", lambda: (None, ws, docs[2].id)),
            ("get_templates_with_creator", lambda: (None, ws, None, True)),
            ("get_templates_with_creator", lambda: (None, None)),
            ("get_template_by_id", lambda: (docs[0].id,)),
            ("get_template_by_id", lambda: (PydanticObjectId(),)),
            ("get_template_by_workspace_id_n_template_id", lambda: (ws, docs[1].id)),
            ("get_template_by_id_with_creator", lambda: (ws, docs[2].id)),
            ("get_v2_template_by_title", lambda: ("v2",)),
            ("get_v2_template_by_title", lambda: ("plain",)),  # not v2
            ("get_v2_template_by_title", lambda: ("missing",)),
        ],
    )
    listed = await postgres.get_templates_with_creator(workspace_id=ws)
    by_title = {t["title"]: t for t in listed}
    assert by_title["from origin"]["imported_from"] == "Origin"
    assert by_title["from origin"]["id"] == docs[2].id
    assert strip(await mongo.get_templates_with_creator(workspace_id=ws)) == strip(
        listed
    )
    await both_raise(
        HTTPException,
        lambda: mongo.get_template_by_id_with_creator(ws, PydanticObjectId()),
        lambda: postgres.get_template_by_id_with_creator(ws, PydanticObjectId()),
    )
    body = StandardFormTemplate(title="Fresh", description="d", fields=[])
    user = User(id=str(PydanticObjectId()), sub="u@example.com")
    assert strip(await mongo.create_new_template(ws, body, user)) == strip(
        await postgres.create_new_template(ws, body, user)
    )
    assert strip(
        await mongo.import_template_to_workspace(gone_ws, docs[0].id)
    ) == strip(await postgres.import_template_to_workspace(gone_ws, docs[0].id))
    body.title = "Renamed"
    await parity(
        mongo,
        postgres,
        [
            ("update_template", lambda: (docs[0].id, body)),
            ("get_template_by_id", lambda: (docs[0].id,)),
            ("delete_template", lambda: (docs[1].id,)),
            ("get_template_by_id", lambda: (docs[1].id,)),
        ],
    )
    await both_raise(
        HTTPException,
        lambda: mongo.delete_template(docs[1].id),
        lambda: postgres.delete_template(docs[1].id),
    )


# ---------------------------------------------------------- media library, consent
def strip_media(value):
    """media_id is minted inside add_media_in_workspace_library (replayed to the
    mirror in dual mode), so the two stores differ on it here."""
    return [{k: v for k, v in item.items() if k != "media_id"} for item in strip(value)]


async def test_media_library(sessions):
    ws = str(PydanticObjectId())
    mongo, postgres = MediaLibraryRepository(), PostgresMediaLibraryRepository(sessions)
    added = {}
    for name, repo in (("mongo", mongo), ("postgres", postgres)):
        added[name] = [
            await repo.add_media_in_workspace_library(
                ws, f"http://x/{n}", "IMAGE", n, f"k/{n}"
            )
            for n in ("Logo", "banner", "logo-dark")
        ]
    assert strip_media(added["mongo"]) == strip_media(added["postgres"])
    for query in (None, "logo", "zzz"):
        assert strip_media(
            await mongo.get_media_library_by_worksapce_id(ws, query)
        ) == strip_media(await postgres.get_media_library_by_worksapce_id(ws, query))
    assert await postgres.get_media_library_by_worksapce_id("other", None) == []
    for name, repo in (("mongo", mongo), ("postgres", postgres)):
        media_id = added[name][1].media_id
        assert (
            await repo.get_single_media_from_workspace_library(ws, media_id)
        ).media_name == "banner"
        assert await repo.delete_media_from_library(ws, media_id) == media_id
        assert await repo.get_single_media_from_workspace_library(ws, media_id) is None
    assert strip_media(
        await mongo.get_media_library_by_worksapce_id(ws, None)
    ) == strip_media(await postgres.get_media_library_by_worksapce_id(ws, None))


async def test_workspace_consent(sessions):
    ws = PydanticObjectId()
    consent = ConsentCamelModel(
        title="Newsletter",
        type="checkbox",
        category="purpose_of_the_form",
        required=False,
    )
    await parity(
        WorkspaceConsentRepo(),
        PostgresWorkspaceConsentRepo(sessions),
        [
            ("get_workspace_consents", lambda: (ws,)),
            ("create_workspace_consent", lambda: (ws, consent)),
            ("get_workspace_consents", lambda: (ws,)),
        ],
    )


async def test_action_parameters_and_secrets(sessions):
    """The Sheets re-consent markers (services/sheets_reconsent.py): one
    action's parameters change, nothing else does (not ``updated_at``), and
    a marker is claimed once."""
    groups, responses = ResponderGroupsRepository(), FormResponseRepository(
        crypto=container.crypto()
    )
    mongo = FormRepository()
    postgres = PostgresFormRepository(sessions, groups, responses)
    a1, a2 = str(PydanticObjectId()), str(PydanticObjectId())
    forms = (
        form(
            "p1",
            "With",
            1,
            parameters={
                a1: [ParameterValue(name="Title", value="Sheet")],
                a2: [ParameterValue(name="Url", value="u")],
            },
            secrets={a1: [ParameterValue(name="Credentials", value="c")]},
        ),
        form("p2", "Without", 2),
    )
    await seed_both((mongo, postgres), "save_form", *forms)
    before = {
        repo: (await repo.get_form_document_by_id("p1")).updated_at
        for repo in (mongo, postgres)
    }

    await parity(
        mongo,
        postgres,
        [
            ("update_action_parameters", lambda: ("p1", a1, {"needs_reconsent": "true"})),
            ("update_action_parameters", lambda: ("p1", a1, {"needs_reconsent": "true"})),
            ("update_action_parameters", lambda: ("p1", a1, None, "skipped")),
            ("update_action_parameters", lambda: ("p1", a1, None, "skipped")),
            ("update_action_parameters", lambda: ("p1", a1, {"m": "t"}, None, "m")),
            ("update_action_parameters", lambda: ("p1", a1, {"m": "t2"}, None, "m")),
            ("update_action_parameters", lambda: ("p1", a1, None, None, None, ["m"])),
            # no parameters at all yet, and an unknown form
            ("update_action_parameters", lambda: ("p2", a1, {"needs_reconsent": "true"})),
            ("update_action_parameters", lambda: ("nope", a1, {"x": "y"})),
            ("get_forms_with_action_secrets", lambda: ([a1],)),
            ("get_forms_with_action_secrets", lambda: ([a2],)),
            ("get_forms_with_action_secrets", lambda: ([],)),
            ("get_form_document_by_id", lambda: ("p1",)),
            ("get_form_document_by_id", lambda: ("p2",)),
        ],
    )
    for repo in (mongo, postgres):
        stored = await repo.get_form_document_by_id("p1")
        assert {p.name: p.value for p in stored.parameters[a1]} == {
            "Title": "Sheet",
            "needs_reconsent": "true",
            "skipped": "2",
        }
        assert [p.value for p in stored.parameters[a2]] == ["u"]
        assert stored.updated_at == before[repo]


async def test_replace_action_credential(sessions):
    """A new Sheets grant (services/sheets_grant_revocation.py): one write
    stores the credential and drops the re-consent markers; the draft's
    previous ciphertext is returned; published versions' copies are replaced;
    other actions, other secrets and ``updated_at`` stay as they were."""
    groups, responses = ResponderGroupsRepository(), FormResponseRepository(
        crypto=container.crypto()
    )
    mongo = FormRepository()
    postgres = PostgresFormRepository(sessions, groups, responses)
    a1, a2 = str(PydanticObjectId()), str(PydanticObjectId())
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
    await seed_both((mongo, postgres), "save_form", draft, form("p2", "Bare", 2))
    await seed_both(
        (mongo, postgres), "save_form_version", version(draft, 1), version(draft, 2)
    )
    before = {
        repo: (await repo.get_form_document_by_id("p1")).updated_at
        for repo in (mongo, postgres)
    }
    markers = ["needs_reconsent", "reconsent_skipped_runs", "reconsent_mailed_at"]

    await parity(
        mongo,
        postgres,
        [
            ("replace_action_credential", lambda: ("p1", a1, "new", markers)),
            # again: the previous one is now the new one, nothing left to drop
            ("replace_action_credential", lambda: ("p1", a1, "new", markers)),
            # no secrets or parameters at all yet, and an unknown form
            ("replace_action_credential", lambda: ("p2", a1, "first", markers)),
            ("replace_action_credential", lambda: ("nope", a1, "x", markers)),
            ("get_form_document_by_id", lambda: ("p1",)),
            ("get_form_document_by_id", lambda: ("p2",)),
        ],
    )
    for repo in (mongo, postgres):
        stored = await repo.get_form_document_by_id("p1")
        assert {p.name: p.value for p in stored.parameters[a1]} == {"Title": "Sheet"}
        assert {s.name: s.value for s in stored.secrets[a1]} == {
            "Credentials": "new",
            "Other": "kept",
        }
        assert [p.value for p in stored.parameters[a2]] == ["true"]
        assert [s.value for s in stored.secrets[a2]] == ["other-action"]
        assert stored.updated_at == before[repo]
        bare = await repo.get_form_document_by_id("p2")
        assert [(s.name, s.value) for s in bare.secrets[a1]] == [("Credentials", "first")]
        published_versions = await repo.get_versions_of_form("p1")
        assert [v.version for v in published_versions] == [1, 2]
        for published in published_versions:
            assert {s.name: s.value for s in published.secrets[a1]} == {
                "Credentials": "new",
                "Other": "kept",
            }
            assert [s.value for s in published.secrets[a2]] == ["other-action"]
