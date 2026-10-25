"""The read-only check counts stored values with the ciphertext prefix that do
not decrypt, per store and field, without printing ids or values and without
changing anything."""

import json

import pytest
from beanie import PydanticObjectId
from common.models.standard_form import RespondentFeedback
from common.services.crypto_service import crypto_service

from backend.app.container import container
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from scripts.check_undecryptable_values import (
    MongoStore,
    PostgresStore,
    _parse,
    default_opener,
    run,
)
from tests.conftest import TEST_MONGO_DB, _postgres_configured, _truncate_postgres

pytestmark = pytest.mark.asyncio

WS = PydanticObjectId("65e5501d00000000000000a1")
# a leak-check needle too: long, so it can only match if the form id is printed
FORM_ID = "form-id-never-printed"


def _encrypted(workspace_id, form_id, value):
    return crypto_service.encrypt(
        workspace_id=workspace_id, form_id=form_id, data=value
    )


def _documents():
    link = WorkspaceFormDocument(
        id=PydanticObjectId("65e5501d0000000000000001"),
        workspace_id=WS,
        form_id=FORM_ID,
        user_id="u1",
    )

    def response(response_id, **extra):
        return FormResponseDocument(
            id=PydanticObjectId(), response_id=response_id, form_id=FORM_ID, **extra
        )

    def feedback(message):
        return RespondentFeedback(id="e", status="Open", message=message)

    responses = [
        # genuine ciphertext everywhere
        response(
            "ok",
            workspace_id=WS,
            answers=_encrypted(WS, FORM_ID, '{"q": "a"}'),
            hidden_fields=_encrypted(WS, FORM_ID, '{"utm": "x"}'),
            respondent_feedback=[feedback(_encrypted(WS, FORM_ID, "v1:fine"))],
        ),
        # stored before encrypt stopped passing prefixed plaintext through
        response(
            "legacy",
            workspace_id=WS,
            answers=_encrypted(WS, FORM_ID, "{}"),
            respondent_feedback=[
                feedback(b"v1:secret note"),
                feedback(_encrypted(WS, FORM_ID, "later")),
            ],
        ),
        # damaged, and no workspace stamped: tried under the form's link
        response("damaged", internal_answers=b"v1:\x00\xff\x10binary"),
        # plaintext without the prefix is not this check's business
        response("plain", workspace_id=WS, answers={"q": {"text": "a"}}),
    ]
    return link, responses


async def _mongo_store():
    link, responses = _documents()
    for document in responses:
        await document.save()
    # the form's link is in Postgres only (4.1): the Mongo store reads it there
    await PostgresWorkspaceFormRepository(container.pg_sessionmaker(), None).upsert(link)
    return MongoStore(
        container.database_client()[TEST_MONGO_DB],
        links=PostgresStore(container.pg_engine()),
    )


async def _postgres_store():
    link, responses = _documents()
    sessions = container.pg_sessionmaker()
    await PostgresWorkspaceFormRepository(sessions, None).upsert(link)
    responses_repo = PostgresFormResponseRepository(sessions, None, None)
    for document in responses:
        await responses_repo.upsert(document)
    return PostgresStore(container.pg_engine())


@pytest.fixture(params=["mongo", "postgres"])
async def store(request):
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    if request.param == "postgres":
        return await _postgres_store()
    return await _mongo_store()


async def test_counts_values_that_do_not_decrypt(store):
    before = await store.batch(None, 100)

    report = await run([store], default_opener(), batch_size=2)

    counts = report["stores"][store.name]
    assert counts["responses"] == 4
    assert counts["does_not_decrypt"] == 2
    assert counts["fields"] == {
        "answers": {"prefixed": 2, "decrypts": 2},
        "hidden_fields": {"prefixed": 1, "decrypts": 1},
        "internal_answers": {
            "prefixed": 1,
            "does_not_decrypt": 1,
            "of_which_binary": 1,
        },
        "respondent_feedback.message": {
            "prefixed": 3,
            "decrypts": 2,
            "does_not_decrypt": 1,
            "of_which_text": 1,
        },
    }
    # counts only, and nothing written
    printed = json.dumps(report)
    for secret in ("secret note", "legacy", "damaged", str(WS), FORM_ID):
        assert secret not in printed
    assert await store.batch(None, 100) == before


def test_arguments():
    assert _parse([]).store == "all"
    assert _parse(["--store", "postgres", "--batch-size", "10"]).batch_size == 10
