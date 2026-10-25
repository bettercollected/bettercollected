"""Rotating MASTER_ENCRYPTION_KEYSET end to end, per store (Mongo, Postgres,
and both as in a dual write mode): add a key, re-encrypt everything under it,
drop the old key. Dry run changes nothing, a rerun is a no-op, drop-old
refuses while an old key is in use, and nothing printed carries a keyset,
an answer or a credential."""

import json
import os
import stat

import pytest
from beanie import PydanticObjectId
from bson import ObjectId
from sqlalchemy import text

from backend.admin.tasks.spec import Refusal
from backend.app.container import container
from backend.app.repositories.postgres.forms import PostgresWorkspaceFormRepository
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from common.db.canonical import canonical_document, checksum
from common.models.standard_form import RespondentFeedback
from common.services.crypto_service import crypto_service
from common.services.keyset import (
    CryptoService,
    ciphertext_key_id,
    encode_keyset,
    parse_keyset,
)
from scripts.rotate_response_keyset import (
    GOOGLE_CREDENTIALS,
    RESPONSES,
    MongoStore,
    PostgresStore,
    _main,
    plan_drop_old,
    plan_stores,
)
from tests.conftest import (
    TEST_MONGO_DB,
    TEST_MONGO_URI,
    _postgres_configured,
    _truncate_postgres,
)

pytestmark = pytest.mark.asyncio

WS_A = PydanticObjectId("65e5501d00000000000000a1")
WS_B = PydanticObjectId("65e5501d00000000000000b2")
OLD_KEY = crypto_service.primary_key_id
SECRETS = ("an answer", "a hidden value", "an internal note", "a message", "refresh-me")


def _enc(workspace, form_id, plaintext: str) -> bytes:
    return crypto_service.encrypt(
        workspace_id=workspace, form_id=form_id, data=plaintext
    )


class Data:
    """The records, and what each encrypted value must decrypt to."""

    def __init__(
        self,
        with_orphan: bool = False,
        with_mixed: bool = False,
        with_credentials: bool = True,
        with_legacy_plaintext: bool = False,
    ):
        self.expected = {}  # (target, record id, path) -> (context, plaintext)
        self.links = [
            WorkspaceFormDocument(
                id=PydanticObjectId(), workspace_id=WS_A, form_id="f1", user_id="u"
            ),
            WorkspaceFormDocument(
                id=PydanticObjectId(), workspace_id=WS_A, form_id="f2", user_id="u"
            ),
            WorkspaceFormDocument(
                id=PydanticObjectId(), workspace_id=WS_B, form_id="f2", user_id="u"
            ),
        ]
        self.responses = []

        def response(form_id, workspace, stamped=True, **values):
            document = FormResponseDocument(
                id=PydanticObjectId(),
                form_id=form_id,
                workspace_id=workspace if stamped else None,
            )
            rid = str(document.id)
            for field, plaintext in values.items():
                if field == "respondent_feedback":
                    document.respondent_feedback = [
                        RespondentFeedback(
                            status="Selected",
                            message=_enc(workspace, form_id, plaintext),
                        ),
                        RespondentFeedback(status="Closed", message=None),
                    ]
                    path = ("respondent_feedback", 0, "message")
                else:
                    setattr(document, field, _enc(workspace, form_id, plaintext))
                    path = (field,)
                self.expected[("responses", rid, path)] = (
                    (str(workspace), form_id),
                    plaintext.encode(),
                )
            self.responses.append(document)

        # stamped with its workspace; every encrypted field
        response(
            "f1",
            WS_A,
            answers=json.dumps({"q1": {"text": "an answer"}}),
            hidden_fields=json.dumps({"ref": "a hidden value"}),
            internal_answers=json.dumps({"i1": {"text": "an internal note"}}),
            respondent_feedback="a message",
        )
        # stored before responses carried their workspace: found by the links
        response("f1", WS_A, stamped=False, answers='{"q1": "an answer"}')
        response("f2", WS_B, stamped=False, answers='{"q1": "an answer"}')
        # nothing encrypted
        self.responses.append(
            FormResponseDocument(
                id=PydanticObjectId(),
                form_id="f1",
                workspace_id=WS_A,
                answers={"q1": {"text": "plain"}},
            )
        )
        if with_orphan:  # no workspace, no link: nothing can open it
            response("gone", WS_A, stamped=False, answers='{"q1": "an answer"}')
        if with_mixed:
            # unstamped, its form in two workspaces, its values encrypted for
            # different ones: each value has to find its own context
            mixed = FormResponseDocument(
                id=PydanticObjectId(),
                form_id="f2",
                answers=_enc(WS_A, "f2", '{"q1": "an answer"}'),
                hidden_fields=_enc(WS_B, "f2", '{"ref": "a hidden value"}'),
            )
            self.responses.append(mixed)
            self.expected[("responses", str(mixed.id), ("answers",))] = (
                (str(WS_A), "f2"),
                b'{"q1": "an answer"}',
            )
            self.expected[("responses", str(mixed.id), ("hidden_fields",))] = (
                (str(WS_B), "f2"),
                b'{"ref": "a hidden value"}',
            )

        if with_legacy_plaintext:
            # a feedback message stored before CryptoService.encrypt stopped
            # passing "v1:..." through: looks like ciphertext, is plaintext
            legacy = FormResponseDocument(
                id=PydanticObjectId(),
                form_id="f1",
                workspace_id=WS_A,
                answers=_enc(WS_A, "f1", '{"q1": "an answer"}'),
                respondent_feedback=[
                    RespondentFeedback(status="Closed", message=b"v1:a message")
                ],
            )
            self.responses.append(legacy)
            self.expected[("responses", str(legacy.id), ("answers",))] = (
                (str(WS_A), "f1"),
                b'{"q1": "an answer"}',
            )

        self.credentials = []
        if not with_credentials:
            return
        credential_id = ObjectId()
        self.credentials = [
            {
                "_id": credential_id,
                "user_id": "user-1",
                "email": "someone@example.com",
                "provider": "google",
                "credentials": crypto_service.encrypt(
                    "personal", form_id="user-1", data='{"token": "refresh-me"}'
                ),
            }
        ]
        self.expected[("google-credentials", str(credential_id), ("credentials",))] = (
            ("personal", "user-1"),
            b'{"token": "refresh-me"}',
        )

    async def to_mongo(self, responses=True, credentials=True):
        db = container.database_client()[TEST_MONGO_DB]
        for document in (*self.links, *self.responses) if responses else ():
            await document.save()
        if self.credentials and credentials:
            await db[GOOGLE_CREDENTIALS.collection].insert_many(
                [dict(c) for c in self.credentials]
            )

    async def to_postgres(self, responses=True, credentials=True):
        sessions = container.pg_sessionmaker()
        links = PostgresWorkspaceFormRepository(sessions, None)
        repository = PostgresFormResponseRepository(sessions, None, None)
        for link in self.links if responses else ():
            await links.upsert(link)
        for document in self.responses if responses else ():
            await repository.upsert(document)
        async with container.pg_engine().begin() as conn:
            for credential in self.credentials if credentials else ():
                doc = canonical_document(credential)
                await conn.execute(
                    text(
                        "INSERT INTO google.oauth_credentials (id, doc, _bc_checksum) "
                        "VALUES (:id, CAST(:doc AS jsonb), :checksum)"
                    ),
                    {
                        "id": str(credential["_id"]),
                        "doc": json.dumps(doc),
                        "checksum": checksum(doc),
                    },
                )


@pytest.fixture
async def google_table():
    """google.oauth_credentials as the integration's migrations create it
    (the columns the rotation touches), unless this database has it."""
    if not _postgres_configured():
        yield None
        return
    engine = container.pg_engine()
    async with engine.begin() as conn:
        exists = (
            await conn.execute(text("SELECT to_regclass('google.oauth_credentials')"))
        ).scalar()
        schema_exists = (
            await conn.execute(
                text("SELECT 1 FROM pg_namespace WHERE nspname = 'google'")
            )
        ).scalar()
        if not exists:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS google"))
            await conn.execute(
                text(
                    "CREATE TABLE google.oauth_credentials (id text PRIMARY KEY, "
                    "doc jsonb NOT NULL, _bc_checksum text NOT NULL)"
                )
            )
        await conn.execute(text("DELETE FROM google.oauth_credentials"))
    yield
    async with engine.begin() as conn:
        if exists:
            await conn.execute(text("DELETE FROM google.oauth_credentials"))
        else:
            await conn.execute(text("DROP TABLE google.oauth_credentials"))
            if not schema_exists:
                await conn.execute(text("DROP SCHEMA google"))


# the write mode the services would run with, per store choice
WRITE_MODES = {
    "mongo": ("mongo", "mongo"),
    "postgres": ("postgres", "postgres"),
    "both": ("dual", "mongo"),
}


@pytest.fixture(params=["mongo", "postgres", "both"])
async def stores(request, google_table, monkeypatch):
    """Points the script's settings at the test stores, with the write mode
    that makes ``auto`` (what drop-old always uses) pick the chosen ones."""
    # every choice needs Postgres: the Google credentials are there (4.1)
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    for name in list(os.environ):
        if name.startswith(("DB_WRITE_MODE__", "DB_READ_SOURCE__")):
            monkeypatch.delenv(name)
    write, read = WRITE_MODES[request.param]
    monkeypatch.setenv("DB_WRITE_MODE", write)
    monkeypatch.setenv("DB_READ_SOURCE", read)
    return request.param


@pytest.fixture(autouse=True)
def _only_the_chosen_stores(request, monkeypatch):
    """For this script's tests: only the chosen stores are configured, since
    ``auto`` (reencrypt) also covers any other configured store (see
    test_drop_old_scans_a_configured_store_the_services_no_longer_write).

    drop-old needs both stores unless Mongo is retired: with ``mongo`` it
    also scans the (emptied) Postgres responses, with ``postgres`` it runs with
    ``--mongo-retired`` (the services' write mode is postgres everywhere).
    The Google credentials are in Postgres in every choice (the Google Forms
    integration writes Postgres alone since 4.1), so GOOGLE_DATABASE_URL stays."""
    if "stores" not in request.fixturenames:
        return
    choice = request.getfixturevalue("stores")
    if choice == "mongo":
        url = os.environ.get("DATABASE_URL", "")
        monkeypatch.setitem(DROP_OLD, "env", {"DATABASE_URL": url})
        monkeypatch.setenv("DATABASE_URL", "")
    elif choice == "postgres":
        monkeypatch.setenv("MONGO_URI", "")
        monkeypatch.setitem(DROP_OLD, "args", ["--mongo-retired"])


# per store choice, the stores holding each target, primary first. The Google
# credentials are in Postgres in every choice: the Google Forms integration
# writes Postgres alone since 4.1; with ``both`` a copy from 4.0 is also left in
# Mongo.
TARGET_STORES = {
    "mongo": {"responses": ["mongo"], "google-credentials": ["postgres"]},
    "postgres": {"responses": ["postgres"], "google-credentials": ["postgres"]},
    "both": {
        "responses": ["mongo", "postgres"],
        "google-credentials": ["postgres", "mongo"],
    },
}


async def seed(store_choice, data):
    held = TARGET_STORES[store_choice]
    for name, store in (("mongo", data.to_mongo), ("postgres", data.to_postgres)):
        responses = name in held["responses"]
        credentials = name in held["google-credentials"]
        if responses or credentials:
            await store(responses=responses, credentials=credentials)


def drop_old_records(store_choice, responses, google):
    """drop-old's record counts: both stores (Postgres alone with
    ``--mongo-retired``), 0 where the choice keeps none of the target."""
    scanned = ["postgres"] if store_choice == "postgres" else ["mongo", "postgres"]

    def counts(target, value):
        held = store_names(store_choice, target)
        return {name: value if name in held else 0 for name in scanned}

    return {
        "responses": counts("responses", responses),
        "google-credentials": counts("google-credentials", google),
    }


def store_names(store_choice, target="responses"):
    return TARGET_STORES[store_choice][target]


def store_objects(store_choice):
    for target in (RESPONSES, GOOGLE_CREDENTIALS):
        for name in store_names(store_choice, target.name):
            if name == "mongo":
                yield MongoStore(container.database_client()[TEST_MONGO_DB], target)
            else:
                yield PostgresStore(container.pg_engine(), target)


async def stored_values(store_choice):
    """(store, target, record id, path) -> the stored ciphertext."""
    found = {}
    for store in store_objects(store_choice):
        for record in await store.batch(None, 1000):
            for path, value in store.target.values(record):
                found[(store.name, store.target.name, record["id"], path)] = value
    return found


async def postgres_checksums_agree():
    async with container.pg_engine().connect() as conn:
        for table in ("app.form_responses", "google.oauth_credentials"):
            rows = await conn.execute(text(f"SELECT doc, _bc_checksum FROM {table}"))
            for doc, stored in rows:
                assert stored == checksum(doc)


# what the ``stores`` choice adds to a drop-old run (_only_the_chosen_stores)
DROP_OLD = {"args": [], "env": {}}


async def cli(capsys, *argv):
    argv = list(argv)
    saved = {}
    if argv[:1] == ["drop-old"]:
        argv += DROP_OLD["args"]
        saved = {name: os.environ.get(name) for name in DROP_OLD["env"]}
        os.environ.update(DROP_OLD["env"])
    try:
        code = await _main(argv)
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    captured = capsys.readouterr()
    out = captured.out
    return code, (json.loads(out) if out.strip().startswith("{") else captured.err)


def assert_nothing_secret(text_out: str, *keysets: str):
    for secret in (*SECRETS, *keysets):
        assert secret not in text_out
    assert str(WS_A) not in text_out


async def add_key_and_deploy(capsys, monkeypatch, tmp_path):
    """add-key, then what step 3 of the runbook does: the services (here, the
    environment the script runs in) get the new keyset."""
    rotated_file = tmp_path / "rotated.keyset"
    code, _ = await cli(capsys, "add-key", "--out", str(rotated_file))
    assert code == 0
    value = rotated_file.read_text().strip()
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", value)
    return rotated_file, value, parse_keyset(value).primary_key_id


def primary_of(store_choice, target="responses"):
    return store_names(store_choice, target)[0]


async def test_rotation_end_to_end(stores, tmp_path, capsys, monkeypatch):
    data = Data()
    await seed(stores, data)
    old_keyset = os.environ["MASTER_ENCRYPTION_KEYSET"]
    rotated_file, final_file = tmp_path / "rotated.keyset", tmp_path / "final.keyset"
    batches = ["--batch-size", "2"]

    # add-key: the current keys plus a new primary, to a file only its owner reads
    code, added = await cli(capsys, "add-key", "--out", str(rotated_file))
    assert code == 0
    assert stat.S_IMODE(os.stat(rotated_file).st_mode) == 0o600
    rotated_value = rotated_file.read_text().strip()
    rotated = parse_keyset(rotated_value)
    new_key = rotated.primary_key_id
    assert new_key != OLD_KEY and added["primary_key_id"] == new_key
    assert sorted(added["key_ids"]) == sorted([OLD_KEY, new_key])
    assert_nothing_secret(json.dumps(added), old_keyset, rotated_value)
    # it never overwrites a file
    code, _ = await cli(capsys, "add-key", "--out", str(rotated_file))
    assert code == 2 and rotated_file.read_text().strip() == rotated_value

    before = await stored_values(stores)
    assert before and all(ciphertext_key_id(v) == OLD_KEY for v in before.values())

    # dry run: counts only (allowed before the new keyset is deployed)
    code, report = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), "--dry-run", *batches
    )
    assert code == 0 and report["mode"] == "dry-run"
    responses = report["targets"]["responses"]
    for name in store_names(stores):
        assert responses[name] == {
            "records": 4,
            "records_stale": 3,
            "values": 6,
            "values_stale": 6,
            f"values_key_{OLD_KEY}": 6,
        }
    for name in store_names(stores, "google-credentials"):
        assert report["targets"]["google-credentials"][name]["values_stale"] == 1
    assert await stored_values(stores) == before

    # deploy the new keyset; then drop-old refuses while the old key is in use
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", rotated_value)
    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file)
    )
    assert code == 1 and refused["values_stale"] > 0 and "refused" in refused
    assert not final_file.exists()

    # re-encrypt
    code, report = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), *batches
    )
    assert code == 0 and report["mode"] == "apply"
    primary = primary_of(stores)
    counts = report["targets"]["responses"][primary]
    assert counts["records_reencrypted"] == 3 and counts["values_reencrypted"] == 6
    assert counts["records_current"] == 1
    assert "records_unopenable" not in counts
    google_primary = primary_of(stores, "google-credentials")
    assert report["targets"]["google-credentials"][google_primary]["values_reencrypted"] == 1
    if stores == "both":
        # the mirror got the primary's ciphertexts, nothing left to do there
        assert counts["mirror_records_copied"] == 3
        assert "records_reencrypted" not in report["targets"]["responses"]["postgres"]
    assert_nothing_secret(json.dumps(report), old_keyset, rotated_value)

    after = await stored_values(stores)
    assert after.keys() == before.keys()
    assert all(ciphertext_key_id(v) == new_key for v in after.values())
    if stores == "both":  # the two stores hold the same bytes
        for (store, target, rid, path), value in after.items():
            if store == "mongo":
                assert after[("postgres", target, rid, path)] == value
    await postgres_checksums_agree()

    # everything reads back, with the new key alone
    def reads_back(cipher):
        for (_, target, rid, path), value in after.items():
            context, plaintext = data.expected[(target, rid, path)]
            assert cipher.decrypt(*context, value) == plaintext

    reads_back(CryptoService(rotated_value))

    # a rerun is a no-op
    code, again = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), *batches
    )
    assert code == 0
    assert "records_reencrypted" not in again["targets"]["responses"][primary]
    assert await stored_values(stores) == after

    # drop-old: the new key only, with every store's record count in the report
    code, dropped = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file)
    )
    assert code == 0, dropped
    assert dropped["dropped_key_ids"] == [OLD_KEY]
    assert dropped["records"] == drop_old_records(stores, responses=4, google=1)
    assert "note" not in dropped  # no Typeform caveat since its removal
    assert stat.S_IMODE(os.stat(final_file).st_mode) == 0o600
    final_value = final_file.read_text().strip()
    final = parse_keyset(final_value)
    assert [k.key_id for k in final.key] == [new_key]
    reads_back(CryptoService(final_value))
    assert_nothing_secret(json.dumps(dropped), old_keyset, rotated_value, final_value)


async def test_writes_only_with_the_deployed_keyset(
    stores, tmp_path, capsys, monkeypatch
):
    """Until the services run the new keyset, nothing is re-encrypted under it
    and no key is dropped."""
    await seed(stores, Data())
    before = await stored_values(stores)
    rotated_file = tmp_path / "rotated.keyset"
    assert (await cli(capsys, "add-key", "--out", str(rotated_file)))[0] == 0
    new_key = parse_keyset(rotated_file.read_text()).primary_key_id

    # the environment still has the old keyset (the services were not updated)
    code, err = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 2
    assert "is not the primary of the deployed MASTER_ENCRYPTION_KEYSET" in err
    assert str(new_key) in err and str(OLD_KEY) in err
    code, err = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(tmp_path / "final.keyset"),
    )
    assert code == 2 and "Deploy the keyset to every service first" in err
    assert not (tmp_path / "final.keyset").exists()
    # nothing at all in the environment
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYSET")
    code, err = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 2 and "MASTER_ENCRYPTION_KEYSET is not set here" in err
    assert await stored_values(stores) == before


@pytest.mark.parametrize(
    "narrowing", [["--target", "responses"], ["--store", "mongo"], ["--store", "both"]]
)
async def test_drop_old_refuses_a_narrowed_selection(
    narrowing, tmp_path, capsys, monkeypatch
):
    rotated_file, _, _ = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    final_file = tmp_path / "final.keyset"
    code, err = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(final_file),
        *narrowing,
    )
    assert code == 2
    assert "always checks every target in every store" in err
    assert not final_file.exists()


async def test_drop_old_refuses_an_empty_store(stores, tmp_path, capsys, monkeypatch):
    """A store with no records may be the wrong database: not clean by default."""
    await seed(stores, Data(with_credentials=False))
    rotated_file, _, new_key = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    assert (await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file)))[0] == 0
    final_file = tmp_path / "final.keyset"

    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file)
    )
    assert code == 1 and refused["values_stale"] == 0
    assert refused["records"] == drop_old_records(stores, responses=4, google=0)
    # empty where the Google integration writes: Postgres
    assert "google-credentials in postgres" in refused["refused"]
    assert "google-credentials in mongo" not in refused["refused"]
    assert "--allow-empty" in refused["refused"]
    assert not final_file.exists()

    code, dropped = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(final_file),
        "--allow-empty",
    )
    assert code == 0, dropped
    assert [k.key_id for k in parse_keyset(final_file.read_text()).key] == [new_key]


async def test_each_value_finds_its_own_context(stores, tmp_path, capsys, monkeypatch):
    """A response stored before it carried its workspace, with values
    encrypted for different workspaces of its form, is re-encrypted whole."""
    data = Data(with_mixed=True)
    await seed(stores, data)
    rotated_file, rotated_value, new_key = await add_key_and_deploy(
        capsys, monkeypatch, tmp_path
    )

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 0
    counts = report["targets"]["responses"][primary_of(stores)]
    assert counts["records_reencrypted"] == 4 and counts["values_reencrypted"] == 8
    assert "records_unopenable" not in counts

    after = await stored_values(stores)
    cipher = CryptoService(rotated_value)
    for (_, target, rid, path), value in after.items():
        assert ciphertext_key_id(value) == new_key
        context, plaintext = data.expected[(target, rid, path)]
        assert cipher.decrypt(*context, value) == plaintext
    code, _ = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(tmp_path / "final.keyset"),
    )
    assert code == 0


async def test_drop_old_refuses_while_a_record_cannot_be_reencrypted(
    stores, tmp_path, capsys, monkeypatch
):
    """A value no context opens stays under the old key, and so does the key."""
    await seed(stores, Data(with_orphan=True))
    rotated_file, _, _ = await add_key_and_deploy(capsys, monkeypatch, tmp_path)

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 0
    counts = report["targets"]["responses"][primary_of(stores)]
    assert counts["records_unopenable"] == 1 and counts["values_unopenable"] == 1

    code, refused = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(tmp_path / "final.keyset"),
    )
    assert code == 1 and refused["values_stale"] >= 1
    assert not (tmp_path / "final.keyset").exists()


async def test_a_legacy_plaintext_with_the_prefix_is_left_and_blocks_drop_old(
    stores, tmp_path, capsys, monkeypatch
):
    """A value that only looks like ciphertext reads as unreadable: the rest of
    its record is re-encrypted, the value is left as it is and counted, and
    the old key stays (scripts.check_undecryptable_values finds such values)."""
    data = Data(with_legacy_plaintext=True)
    await seed(stores, data)
    rotated_file, _, new_key = await add_key_and_deploy(capsys, monkeypatch, tmp_path)

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 0
    counts = report["targets"]["responses"][primary_of(stores)]
    assert counts["records_unopenable"] == 1 and counts["values_unopenable"] == 1
    assert counts["records_reencrypted"] == 4  # the legacy record's answers too
    assert "a message" not in json.dumps(report)
    after = await stored_values(stores)
    legacy = [v for v in after.values() if v == b"v1:a message"]
    assert len(legacy) == len(store_names(stores))  # untouched in every store
    assert all(
        ciphertext_key_id(v) == new_key for v in after.values() if v != b"v1:a message"
    )

    code, refused = await cli(
        capsys,
        "drop-old",
        "--keyset-file",
        str(rotated_file),
        "--out",
        str(tmp_path / "final.keyset"),
    )
    assert code == 1 and refused["values_stale"] >= 1
    assert not (tmp_path / "final.keyset").exists()


async def test_an_interrupted_run_resumes(stores, tmp_path, capsys, monkeypatch):
    data = Data()
    await seed(stores, data)
    rotated_file, _, new_key = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    common = ["--target", "responses", "--batch-size", "1"]

    # stops after one record, as if interrupted
    code, first = await cli(
        capsys,
        "reencrypt",
        "--keyset-file",
        str(rotated_file),
        "--limit",
        "1",
        *common,
    )
    primary = primary_of(stores)
    assert code == 0
    assert first["targets"]["responses"][primary]["records_reencrypted"] == 1
    keys = [ciphertext_key_id(v) for v in (await stored_values(stores)).values()]
    assert new_key in keys and OLD_KEY in keys

    code, second = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), *common
    )
    assert code == 0
    assert second["targets"]["responses"][primary]["records_reencrypted"] == 2
    values = await stored_values(stores)
    responses = {k: v for k, v in values.items() if k[1] == "responses"}
    assert all(ciphertext_key_id(v) == new_key for v in responses.values())


async def test_a_value_changed_meanwhile_is_left_for_the_next_run():
    """Compare-and-set: the store keeps what the application wrote."""
    data = Data()
    await data.to_mongo()
    store = MongoStore(container.database_client()[TEST_MONGO_DB], RESPONSES)
    record = (await store.batch(None, 1))[0]
    (path, old), *_ = RESPONSES.values(record)
    assert not await store.write(record["id"], [(path, b"v1:not-what-is-stored", b"x")])
    assert (await store.batch(None, 1))[0][path[0]] == old


async def test_refuses_to_reencrypt_under_a_published_primary(capsys, monkeypatch):
    """Re-encrypting under the published key would change nothing: add a key first."""
    if not crypto_service.published_key_in_keyset:
        pytest.skip("the test keyset is not the published one (CI's is)")
    code = await _main(["reencrypt", "--store", "mongo"])
    assert code == 2
    assert "run add-key first" in capsys.readouterr().err
    # counting is still allowed: it is how to see what a rotation would do
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    args = ["reencrypt", "--dry-run", "--store", "mongo", "--target", "responses"]
    assert await _main(args) == 0


async def test_a_written_keyset_reads_as_the_services_read_it():
    value = encode_keyset(parse_keyset(os.environ["MASTER_ENCRYPTION_KEYSET"]))
    assert CryptoService(value).primary_key_id == OLD_KEY


# --- the store rule (as the keyset tasks: responses_common.plan_task_stores) ---

PG_URL = "postgresql+asyncpg://user@db.invalid/app"


def _env(**values):
    base = {"MONGO_URI": "mongodb://db.invalid", "DATABASE_URL": PG_URL}
    return {k: v for k, v in {**base, **values}.items() if v is not None}


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("mongo", ["mongo", "postgres"]),
        ("dual", ["mongo", "postgres"]),
        ("postgres_primary_dual", ["postgres", "mongo"]),
        ("postgres", ["postgres", "mongo"]),
        ("DUAL", ["mongo", "postgres"]),
    ],
)
async def test_auto_follows_the_write_mode_primary_first(mode, expected):
    """The written stores, primary first, then any other configured store."""
    assert plan_stores(RESPONSES, "auto", _env(DB_WRITE_MODE=mode)) == expected
    only_mongo = _env(DB_WRITE_MODE=mode, DATABASE_URL=None)
    if mode == "mongo":
        assert plan_stores(RESPONSES, "auto", only_mongo) == ["mongo"]
    else:  # a store the services write is not configured
        with pytest.raises(Refusal, match="store_not_configured"):
            plan_stores(RESPONSES, "auto", only_mongo)


async def test_auto_reads_the_group_override_first():
    env = _env(DB_WRITE_MODE__responses="postgres", DB_WRITE_MODE="mongo")
    assert plan_stores(RESPONSES, "auto", env)[0] == "postgres"
    # the Google credentials are in Postgres only (4.1): no write mode is read
    assert plan_stores(GOOGLE_CREDENTIALS, "auto", env)[0] == "postgres"
    for google in ("mongo", "dual", None):
        env = _env(DB_WRITE_MODE__GOOGLE=google, MONGO_URI=None)
        # the Google credentials' Postgres URL falls back to DATABASE_URL
        assert plan_stores(GOOGLE_CREDENTIALS, "auto", env) == ["postgres"]
        # the responses follow the services' default (mongo), not configured here
        with pytest.raises(Refusal, match="store_not_configured"):
            plan_stores(RESPONSES, "auto", env)


@pytest.mark.parametrize("mode", ["mongodb", "both", "auto"])
async def test_auto_refuses_an_unknown_write_mode(mode):
    """A value that is not a write mode is never guessed at."""
    with pytest.raises(Refusal, match="write_mode_unknown"):
        plan_stores(RESPONSES, "auto", _env(DB_WRITE_MODE=mode))


@pytest.mark.parametrize("mode", [None, "", "  "])
async def test_an_unset_write_mode_is_the_services_default(mode):
    """Unset, as on a fresh stack: the services run on their default (mongo
    while the backend has groups on Mongo), and so does the plan."""
    assert plan_stores(RESPONSES, "auto", _env(DB_WRITE_MODE=mode)) == ["mongo", "postgres"]
    assert plan_drop_old(RESPONSES, False, _env(DB_WRITE_MODE=mode)) == ["mongo", "postgres"]


async def test_a_named_store_needs_no_write_mode_but_a_connection():
    env = _env()
    assert plan_stores(RESPONSES, "mongo", env) == ["mongo"]
    assert plan_stores(RESPONSES, "postgres", env) == ["postgres"]
    assert plan_stores(RESPONSES, "both", env) == ["mongo", "postgres"]
    with pytest.raises(Refusal, match="store_not_configured"):
        plan_stores(RESPONSES, "postgres", _env(DATABASE_URL=""))
    with pytest.raises(Refusal, match="store_not_configured"):
        plan_stores(RESPONSES, "both", _env(MONGO_URI=None))


def _no_write_mode(monkeypatch):
    for name in list(os.environ):
        if name.upper().startswith("DB_WRITE_MODE"):
            monkeypatch.delenv(name)


@pytest.mark.parametrize("command", ["reencrypt", "drop-old"])
async def test_the_cli_refuses_an_unreadable_write_mode_before_opening_anything(
    command, tmp_path, capsys, monkeypatch
):
    rotated_file, _, _ = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    _no_write_mode(monkeypatch)
    monkeypatch.setenv("DB_WRITE_MODE", "mongo-and-postgres")
    monkeypatch.setenv("MONGO_URI", "mongodb://db.invalid:1")
    final_file = tmp_path / "final.keyset"
    args = [command, "--keyset-file", str(rotated_file)]
    if command == "drop-old":
        args += ["--out", str(final_file)]
    code, err = await cli(capsys, *args)
    assert code == 2
    assert "write_mode_unknown" in err and "DB_WRITE_MODE" in err
    assert "db.invalid" not in err
    assert not final_file.exists()


async def test_a_named_store_runs_without_a_write_mode(capsys, monkeypatch):
    _no_write_mode(monkeypatch)
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    args = ["reencrypt", "--dry-run", "--store", "mongo", "--target", "responses"]
    code, report = await cli(capsys, *args)
    assert code == 0 and list(report["targets"]["responses"]) == ["mongo"]


async def test_drop_old_scans_a_configured_store_the_services_no_longer_write(
    google_table, tmp_path, capsys, monkeypatch
):
    """Services on ``mongo`` only, Postgres still reachable and holding old
    values: drop-old refuses until that store is re-encrypted too. An empty
    store the services do not write does not count as a wrong database."""
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    _no_write_mode(monkeypatch)
    monkeypatch.setenv("DB_WRITE_MODE", "mongo")
    await seed("both", Data())
    rotated_file, _, new_key = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    final_file = tmp_path / "final.keyset"
    drop = ["drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file)]

    # only the store the services write is re-encrypted
    code, _ = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), "--store", "mongo"
    )
    assert code == 0
    code, refused = await cli(capsys, *drop)
    assert code == 1 and refused["values_stale"] > 0
    assert refused["targets"]["responses"]["postgres"]["values_stale"] > 0
    assert refused["targets"]["responses"]["mongo"]["values_stale"] == 0
    assert not final_file.exists()

    # auto covers it (Mongo first, as written); then the Postgres responses are
    # emptied: an empty store the services do not write is not refused
    code, _ = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 0
    await _truncate_postgres()
    code, dropped = await cli(capsys, *drop)
    assert code == 0, dropped
    assert dropped["records"]["responses"]["postgres"] == 0
    assert [k.key_id for k in parse_keyset(final_file.read_text()).key] == [new_key]


# --- drop-old: both stores unless Mongo is retired (as keyset.drop_old) ---


@pytest.mark.parametrize(
    "mode, expected",
    [
        ("mongo", ["mongo", "postgres"]),
        ("dual", ["mongo", "postgres"]),
        ("postgres_primary_dual", ["postgres", "mongo"]),
        ("postgres", ["postgres", "mongo"]),
    ],
)
async def test_drop_old_needs_both_stores_whatever_the_write_mode(mode, expected):
    """The write mode only orders the stores; it never leaves one out."""
    assert plan_drop_old(RESPONSES, False, _env(DB_WRITE_MODE=mode)) == expected
    for missing in ({"MONGO_URI": None}, {"DATABASE_URL": None}):
        with pytest.raises(Refusal, match="store_not_configured"):
            plan_drop_old(RESPONSES, False, _env(DB_WRITE_MODE=mode, **missing))
    with pytest.raises(Refusal, match="write_mode_unknown"):
        plan_drop_old(RESPONSES, False, _env(DB_WRITE_MODE="sometimes"))


@pytest.mark.parametrize(
    "modes",
    [
        {"DB_WRITE_MODE": "dual"},
        {"DB_WRITE_MODE": "postgres_primary_dual"},
        {"DB_WRITE_MODE": "dual", "DB_WRITE_MODE__GOOGLE": "postgres"},
        {"DB_WRITE_MODE": "postgres", "DB_WRITE_MODE__RESPONSES": "mongo"},
        # an unset default is not retired, even with both overrides on postgres
        {"DB_WRITE_MODE__RESPONSES": "postgres", "DB_WRITE_MODE__GOOGLE": "postgres"},
        {},
    ],
)
async def test_mongo_retired_is_refused_unless_every_group_is_on_postgres(modes):
    env = _env(MONGO_URI=None, **modes)
    for target in (RESPONSES, GOOGLE_CREDENTIALS):
        with pytest.raises(Refusal, match="mongo_not_retired"):
            plan_drop_old(target, True, env)


async def test_mongo_retired_scans_postgres_alone():
    env = _env(MONGO_URI=None, DB_WRITE_MODE="postgres")
    assert plan_drop_old(RESPONSES, True, env) == ["postgres"]
    assert plan_drop_old(GOOGLE_CREDENTIALS, True, env) == ["postgres"]
    # a stale Google override does not count: that group is Postgres only (4.1)
    env = _env(MONGO_URI=None, DB_WRITE_MODE="POSTGRES", DB_WRITE_MODE__google="dual")
    assert plan_drop_old(RESPONSES, True, env) == ["postgres"]
    assert plan_drop_old(GOOGLE_CREDENTIALS, True, env) == ["postgres"]
    with pytest.raises(Refusal, match="store_not_configured"):
        plan_drop_old(RESPONSES, True, _env(DB_WRITE_MODE="postgres", DATABASE_URL=""))


async def test_drop_old_refuses_when_its_write_mode_is_wrong_and_mongo_is_missing(
    google_table, tmp_path, capsys, monkeypatch
):
    """Services on dual (values in both stores, Mongo's on the old key), the
    script's environment says postgres and has no Mongo connection: drop-old
    must refuse, not scan Postgres alone and drop a key Mongo still uses."""
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    monkeypatch.setenv("MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_MONGO_DB", TEST_MONGO_DB)
    monkeypatch.setenv("GOOGLE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    _no_write_mode(monkeypatch)
    monkeypatch.setenv("DB_WRITE_MODE", "dual")
    await seed("both", Data())
    rotated_file, _, _ = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    # Postgres is re-encrypted; Mongo still holds the old key's values
    code, _ = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), "--store", "postgres"
    )
    assert code == 0
    before = await stored_values("mongo")
    assert any(ciphertext_key_id(v) == OLD_KEY for v in before.values())

    # the script's environment is wrong about the services
    monkeypatch.setenv("DB_WRITE_MODE", "postgres")
    monkeypatch.setenv("MONGO_URI", "")
    final_file = tmp_path / "final.keyset"
    drop = ["drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file)]
    code, err = await cli(capsys, *drop)
    assert code == 2 and "store_not_configured" in err and "--mongo-retired" in err
    assert not final_file.exists()

    # with Mongo reachable again, its old values stop the drop
    monkeypatch.setenv("MONGO_URI", TEST_MONGO_URI)
    code, refused = await cli(capsys, *drop)
    assert code == 1 and refused["targets"]["responses"]["mongo"]["values_stale"] > 0
    assert refused["targets"]["responses"]["postgres"]["values_stale"] == 0
    assert not final_file.exists()
    assert await stored_values("mongo") == before

    # --mongo-retired is refused while any group is not on postgres
    monkeypatch.setenv("MONGO_URI", "")
    monkeypatch.setenv("DB_WRITE_MODE__RESPONSES", "dual")
    code, err = await cli(capsys, *drop, "--mongo-retired")
    assert code == 2 and "mongo_not_retired" in err
    assert not final_file.exists()
