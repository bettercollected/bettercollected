"""The #768 backfill stamps unstamped responses and deletion requests with
their workspace in each store: unambiguously by the form's only workspace, by
the encryption context for a form linked to several workspaces, and never
guesses otherwise (unless told to). Dry run changes nothing; a rerun after
apply is a no-op."""

import json

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.repositories.response_scope import response_scope
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.db.models import FormResponseRow, ResponseDeletionRequestRow
from common.db.canonical import checksum
from common.services.crypto_service import crypto_service
from scripts.backfill_response_workspaces import (
    MongoStore,
    PostgresStore,
    _parse,
    default_opener,
    run,
)
from tests.conftest import TEST_MONGO_DB, _postgres_configured, _truncate_postgres

pytestmark = pytest.mark.asyncio

WS_A = PydanticObjectId("65e5501d00000000000000a1")
WS_B = PydanticObjectId("65e5501d00000000000000b2")


def _answers(workspace_id, form_id):
    return crypto_service.encrypt(
        workspace_id=workspace_id,
        form_id=form_id,
        data=json.dumps({"q1": {"text": "an answer"}}),
    )


def _documents():
    """single: linked to A only; shared: A (first) and B; gone: unlinked."""
    links = [
        WorkspaceFormDocument(
            id=PydanticObjectId("65e5501d0000000000000001"),
            workspace_id=WS_A,
            form_id="single",
            user_id="u1",
        ),
        WorkspaceFormDocument(
            id=PydanticObjectId("65e5501d0000000000000002"),
            workspace_id=WS_A,
            form_id="shared",
            user_id="u1",
        ),
        WorkspaceFormDocument(
            id=PydanticObjectId("65e5501d0000000000000003"),
            workspace_id=WS_B,
            form_id="shared",
            user_id="u2",
        ),
    ]

    def response(response_id, form_id, **extra):
        return FormResponseDocument(
            id=PydanticObjectId(), response_id=response_id, form_id=form_id, **extra
        )

    responses = [
        response("sg_a", "single", answers=_answers(WS_A, "single")),
        response("sh_a", "shared", answers=_answers(WS_A, "shared"), provider="google"),
        response("sh_b", "shared", answers=_answers(WS_B, "shared"), provider="google"),
        response("sh_x", "shared"),  # nothing to authenticate: ambiguous
        response(
            "sh_ok", "shared", answers=_answers(WS_B, "shared"), workspace_id=WS_B
        ),
        response("o1", "gone", answers=_answers(WS_A, "gone")),
    ]
    requests = [
        FormResponseDeletionRequest(id=PydanticObjectId(), form_id=f, response_id=r)
        for f, r in (("shared", "sh_a"), ("shared", "sh_x"), ("single", "sg_a"))
    ]
    return links, responses, requests


async def _mongo_store():
    links, responses, requests = _documents()
    for document in (*responses, *requests):
        await document.save()
    # the forms' links are in Postgres only (4.1): the Mongo store reads them there
    workspace_forms = PostgresWorkspaceFormRepository(container.pg_sessionmaker(), None)
    for link in links:
        await workspace_forms.upsert(link)
    return MongoStore(
        container.database_client()[TEST_MONGO_DB],
        links=PostgresStore(container.pg_engine()),
    )


async def _postgres_store():
    links, responses, requests = _documents()
    sessions = container.pg_sessionmaker()
    workspace_forms = PostgresWorkspaceFormRepository(sessions, None)
    responses_repo = PostgresFormResponseRepository(sessions, None, None)
    for link in links:
        await workspace_forms.upsert(link)
    for document in responses:
        await responses_repo.upsert(document)
    for request in requests:
        await responses_repo.upsert(request, row=ResponseDeletionRequestRow)
    return PostgresStore(container.pg_engine())


async def _stamped(store):
    """response_id -> workspace id (or None), for responses and requests."""
    if isinstance(store, MongoStore):
        result = {}
        for collection in ("form_responses", "responses_deletion_requests"):
            async for row in store.db[collection].find({}):
                key = ("dr:" if collection != "form_responses" else "") + row[
                    "response_id"
                ]
                value = row.get("workspace_id")
                result[key] = str(value) if value else None
        return result
    from sqlalchemy import select

    result = {}
    async with store.engine.connect() as conn:
        for prefix, row in (("", FormResponseRow), ("dr:", ResponseDeletionRequestRow)):
            for response_id, workspace, doc, stored_checksum in await conn.execute(
                select(row.response_id, row.workspace_id, row.doc, row.bc_checksum)
            ):
                # the spine column follows the document; the checksum agrees
                assert stored_checksum == checksum(doc)
                result[prefix + response_id] = workspace
    return result


@pytest.fixture(params=["mongo", "postgres"])
async def store(request):
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    if request.param == "postgres":
        return await _postgres_store()
    return await _mongo_store()


async def test_dry_run_counts_and_changes_nothing(store):
    before = await _stamped(store)

    report = await run([store], apply=False, opens=default_opener())

    counts = report["stores"][store.name]
    assert report["mode"] == "dry-run" and report["encryption_key"] is True
    assert counts["forms_linked_to_several_workspaces"] == 1
    assert counts["responses"] == {
        "unstamped": 5,
        "single_workspace": 1,
        "attributed_by_encryption": 2,
        "ambiguous": 1,
        "orphaned": 1,
    }
    assert counts["deletion_requests"] == {
        "unstamped": 3,
        "from_response": 2,
        "ambiguous": 1,
    }
    assert await _stamped(store) == before
    # counts only: no ids, answers or identities in what it prints
    printed = json.dumps(report)
    for secret in ("sh_a", "sg_a", "an answer", str(WS_A), "shared"):
        assert secret not in printed


async def test_apply_stamps_what_it_can_attribute_and_reruns_as_a_no_op(store):
    report = await run([store], apply=True, opens=default_opener())

    assert report["stores"][store.name]["responses"]["stamped"] == 3
    assert report["stores"][store.name]["deletion_requests"]["stamped"] == 2
    stamped = await _stamped(store)
    assert stamped == {
        "sg_a": str(WS_A),
        "sh_a": str(WS_A),
        "sh_b": str(WS_B),
        "sh_x": None,  # ambiguous: hidden from both until attributed
        "sh_ok": str(WS_B),
        "o1": None,  # its form is in no workspace
        "dr:sh_a": str(WS_A),
        "dr:sh_x": None,
        "dr:sg_a": str(WS_A),
    }

    again = await run([store], apply=True, opens=default_opener())
    counts = again["stores"][store.name]
    assert counts["responses"] == {"unstamped": 2, "ambiguous": 1, "orphaned": 1}
    assert counts["deletion_requests"] == {"unstamped": 1, "ambiguous": 1}
    assert await _stamped(store) == stamped


async def test_without_the_key_shared_forms_stay_ambiguous(store):
    report = await run([store], apply=True, opens=None)

    counts = report["stores"][store.name]["responses"]
    assert counts["ambiguous"] == 3 and "attributed_by_encryption" not in counts
    stamped = await _stamped(store)
    assert stamped["sh_a"] is None and stamped["sh_b"] is None
    assert stamped["sg_a"] == str(WS_A)


def test_there_is_no_option_to_guess_ambiguous_records():
    """An ambiguous record may hold any linked workspace's respondents'
    data: it is never handed to one of them by a rule of thumb."""
    with pytest.raises(SystemExit):
        _parse(["--apply", "--ambiguous", "first-importer"])
    assert vars(_parse(["--apply"])) == {
        "apply": True,
        "store": "all",
        "batch_size": 500,
    }


async def test_after_the_backfill_each_workspace_reads_its_own(store):
    if container.flags().read_source("responses").value != store.name:
        pytest.skip("the routed repositories read the other store in this mode")
    await run([store], apply=True, opens=default_opener())
    repo, links = container.form_response_repo(), container.workspace_form_repo()

    for workspace, expected in ((WS_A, {"sh_a"}), (WS_B, {"sh_b", "sh_ok"})):
        scope = await response_scope(links, workspace, ["shared"])
        listed = await repo.list_by_form_id(scope)
        assert {r.response_id for r in listed} == expected


async def test_mongo_reads_the_links_from_postgres_not_its_frozen_copy():
    """The forms group is in Postgres only since 4.1: a Mongo store reads the
    forms' workspace links there, not the 4.0 copy left in Mongo; that copy
    only where no Postgres is configured (a 4.0 database not imported yet)."""
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    store = await _mongo_store()
    await store.db["workspace_forms"].insert_one(
        {"workspace_id": WS_B, "form_id": "single", "user_id": "u-4.0"}
    )
    links = await store.links()
    assert links["single"] == [str(WS_A)]
    assert links["shared"] == [str(WS_A), str(WS_B)]
    assert (await MongoStore(store.db).links())["single"] == [str(WS_B)]


async def test_the_script_applies_only_after_a_complete_forms_import(monkeypatch, capsys):
    """A link of a form still only in Mongo (an incomplete forms import):
    the dry run goes on with a warning, ``--apply`` refuses (exit 2) and
    writes nothing; once Postgres holds the link it applies."""
    from common.records import to_bson
    from scripts.backfill_response_workspaces import _main
    from tests.conftest import TEST_DATABASE_URL, TEST_MONGO_URI

    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    store = await _mongo_store()
    lost = WorkspaceFormDocument(
        id=PydanticObjectId(), workspace_id=PydanticObjectId(), form_id="shared", user_id="u3"
    )
    await store.db["workspace_forms"].insert_one(to_bson(lost))
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    before = await _stamped(store)

    assert await _main(["--store", "mongo"]) == 0
    assert "forms_import_incomplete" not in capsys.readouterr().err
    assert await _main(["--store", "mongo", "--apply"]) == 2
    assert "refused (forms_import_incomplete)" in capsys.readouterr().err
    assert await _stamped(store) == before

    await PostgresWorkspaceFormRepository(container.pg_sessionmaker(), None).upsert(lost)
    assert await _main(["--store", "mongo", "--apply"]) == 0
    assert await _stamped(store) != before


async def test_the_script_refuses_to_apply_when_mongo_cannot_be_read(monkeypatch, capsys):
    from scripts.backfill_response_workspaces import _main
    from tests.conftest import TEST_DATABASE_URL

    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    monkeypatch.setenv(
        "MONGO_URI", "mongodb://mongo-not-used.invalid/?serverSelectionTimeoutMS=300"
    )
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    assert await _main(["--store", "mongo", "--apply"]) == 2
    assert "refused (store_unreachable)" in capsys.readouterr().err
