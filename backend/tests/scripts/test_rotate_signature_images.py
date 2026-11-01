"""Key rotation and drawn signature images: the images are objects in the file
store, sealed with the response keyset, so the row walk never sees them.
``reencrypt`` re-seals the ones under an old key (the response still serves
its image through the route), and ``drop-old`` refuses while any image is
under a key other than the primary or cannot be checked. The real Tink keyset
and the real submission path are used; the file store is in memory."""

import json

import pytest
from botocore.exceptions import ClientError

from scripts.rotate_images import (
    DrawnImages,
    ObjectStoreError,
    ObjectTooLarge,
    S3Objects,
)
from backend.app.container import container
from backend.app.services import signatures
from backend.app.services.aws_service import AWSS3Service
from common.services.crypto_service import crypto_service
from common.services.keyset import CryptoService, ciphertext_key_id, parse_keyset
from scripts import rotate_response_keyset as script
from tests.app.controllers.test_signature_image_route import _key, _route
from tests.app.controllers.test_signature_question_routes import (  # noqa: F401
    _drawn_response,
    _png,
    signed_form,
    store,
)
from tests.scripts.test_rotate_response_keyset import (  # noqa: F401
    OLD_KEY,
    add_key_and_deploy,
    cli,
    google_table,
)

pytestmark = pytest.mark.asyncio


class Objects:
    """The file store as the rotation sees it, over the route tests' in-memory
    store, with the failures a real one has."""

    def __init__(self, fake):
        self.fake = fake
        self.types = {}
        self.unreachable = set()  # keys whose reads fail
        self.read_only = False  # writes fail
        self.swap_after_first_read = {}  # key -> bytes read next (a concurrent edit)
        self.reads = []
        self.writes = []

    async def read(self, key):
        self.reads.append(key)
        if key in self.unreachable:
            raise ObjectStoreError("EndpointConnectionError")
        if key in self.swap_after_first_read and self.reads.count(key) == 2:
            return self.swap_after_first_read[key]
        data = self.fake.objects.get(key)
        if data is not None and len(data) > signatures.SEALED_MAX_BYTES:
            raise ObjectTooLarge
        return data

    async def write(self, key, data):
        if self.read_only:
            raise ObjectStoreError("ClientError")
        self.writes.append(key)
        self.fake.objects[key] = data
        self.types[key] = signatures.SEALED_CONTENT_TYPE


@pytest.fixture
def objects(store, monkeypatch):
    objects = Objects(store)
    monkeypatch.setattr(script, "make_images", lambda: DrawnImages(objects))
    return objects


@pytest.fixture
def deployed(monkeypatch):
    """The process loads its keyset again after each deploy of a keyset."""
    yield
    crypto_service.reset()


@pytest.fixture
def rotation_env(google_table, monkeypatch, deployed):
    import os

    monkeypatch.setenv("GOOGLE_DATABASE_URL", os.environ.get("DATABASE_URL", ""))
    monkeypatch.setenv("MONGO_URI", "")


def header_key(data):
    return ciphertext_key_id(data)


async def signed_response(client, workspace, signed_form):
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    return form_id, response_id, _key(workspace, form_id, response_id)


async def served(client, workspace, response_id, cookies):
    got = await client.get(_route(workspace, response_id), cookies=cookies)
    return got.status_code, got.content


async def rotate(capsys, monkeypatch, tmp_path):
    rotated_file, value, new_key = await add_key_and_deploy(capsys, monkeypatch, tmp_path)
    crypto_service.reset()
    return rotated_file, value, new_key


def counts_of(report):
    return report["targets"]["responses"]["postgres"]


async def test_reencrypt_reseals_the_image_and_the_route_still_serves_it(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys,
    monkeypatch, test_user_cookies,
):
    form_id, response_id, key = await signed_response(client, workspace, signed_form)
    before = await served(client, workspace, response_id, test_user_cookies)
    assert before[0] == 200 and before[1].startswith(b"\x89PNG")
    sealed = objects.fake.objects[key]
    assert header_key(sealed) == OLD_KEY

    rotated_file, rotated_value, new_key = await rotate(capsys, monkeypatch, tmp_path)

    # dry run: counts only, nothing written, nothing read twice
    code, report = await cli(
        capsys, "reencrypt", "--keyset-file", str(rotated_file), "--dry-run"
    )
    counts = counts_of(report)
    assert code == 0 and report["mode"] == "dry-run"
    assert counts["images_drawn"] == 1 and counts["images_stale"] == 1
    assert counts[f"images_key_{OLD_KEY}"] == 1 and "images_current" not in counts
    assert objects.writes == [] and objects.fake.objects[key] == sealed

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_resealed"] == 1
    assert counts["images_drawn"] == 1
    for bad in ("images_unreadable", "images_unopenable", "images_storage_errors",
                "images_changed_concurrently", "images_readback_failed", "images_missing"):
        assert bad not in counts
    resealed = objects.fake.objects[key]
    assert resealed != sealed and header_key(resealed) == new_key
    assert objects.writes == [key]
    assert objects.types[key] == signatures.SEALED_CONTENT_TYPE
    # still bound to its response, question and file: only the same binding opens it
    cipher = CryptoService(rotated_value)
    context = signatures.image_context(response_id, "sig", "img-1")
    assert cipher.decrypt(str(workspace.id), str(form_id), resealed, context).startswith(b"\x89PNG")
    # and the route serves the same image
    assert await served(client, workspace, response_id, test_user_cookies) == before
    # nothing printed carries a path, an id of a response or an image
    out = json.dumps(report)
    assert key not in out and response_id not in out and "private/" not in out

    # a rerun is a no-op: the object is not written again
    objects.writes.clear()
    code, again = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(again)
    assert code == 0 and "images_resealed" not in counts and counts["images_current"] == 1
    assert objects.writes == [] and objects.fake.objects[key] == resealed


async def test_drop_old_refuses_while_an_image_is_under_the_old_key(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys,
    monkeypatch, test_user_cookies,
):
    form_id, response_id, key = await signed_response(client, workspace, signed_form)
    original = await served(client, workspace, response_id, test_user_cookies)
    rotated_file, rotated_value, new_key = await rotate(capsys, monkeypatch, tmp_path)
    final_file = tmp_path / "final.keyset"

    # the rows go to the new key with the image pass off (what a run made before
    # this pass existed did): the answers are current, the image is not
    monkeypatch.setattr(script, "make_images", lambda: None)
    assert (await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file)))[0] == 0
    monkeypatch.setattr(script, "make_images", lambda: DrawnImages(objects))
    assert header_key(objects.fake.objects[key]) == OLD_KEY

    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file),
        "--allow-empty",
    )
    assert code == 1 and not final_file.exists()
    assert refused["values_stale"] == 0
    assert refused["images_blocking"] == {"images_stale": 1}
    assert "images_blocking" in refused["refused"]
    assert refused["targets"]["responses"]["postgres"][f"images_key_{OLD_KEY}"] == 1
    assert objects.writes == []  # drop-old never writes

    # reencrypt: the rows are current, the image is still found and re-sealed
    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_resealed"] == 1 and counts["records_current"] == 1

    code, dropped = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file), "--out", str(final_file),
        "--allow-empty",
    )
    assert code == 0, dropped
    assert dropped["dropped_key_ids"] == [OLD_KEY] and "images_blocking" not in dropped
    assert dropped["targets"]["responses"]["postgres"]["images_current"] == 1
    final_value = final_file.read_text().strip()
    assert [k.key_id for k in parse_keyset(final_value).key] == [new_key]

    # the services run the final keyset: the image still reads through the route
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYSET", final_value)
    crypto_service.reset()
    assert await served(client, workspace, response_id, test_user_cookies) == original


async def test_a_missing_object_is_reported_and_does_not_block(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys, monkeypatch,
):
    form_id, response_id, key = await signed_response(client, workspace, signed_form)
    rotated_file, _, new_key = await rotate(capsys, monkeypatch, tmp_path)
    del objects.fake.objects[key]

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_missing"] == 1 and "images_resealed" not in counts
    assert "images_storage_errors" not in counts

    code, dropped = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file),
        "--out", str(tmp_path / "final.keyset"), "--allow-empty",
    )
    assert code == 0, dropped
    assert dropped["targets"]["responses"]["postgres"]["images_missing"] == 1
    assert "images_blocking" not in dropped


@pytest.mark.parametrize(
    "tamper,counter",
    [
        ("plaintext", "images_unreadable"),  # an image stored before encryption existed
        ("not_a_sealed_image", "images_unreadable"),
        ("oversized", "images_unreadable"),
    ],
)
async def test_an_unreadable_object_is_reported_and_blocks_drop_old(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys, monkeypatch,
    tamper, counter,
):
    form_id, response_id, key = await signed_response(client, workspace, signed_form)
    rotated_file, _, _ = await rotate(capsys, monkeypatch, tmp_path)
    objects.fake.objects[key] = {
        "plaintext": _png(),
        "not_a_sealed_image": b"v1:",
        "oversized": b"v1:" + b"0" * (signatures.SEALED_MAX_BYTES + 1),
    }[tamper]
    kept = objects.fake.objects[key]

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts[counter] == 1 and "images_resealed" not in counts
    assert objects.fake.objects[key] == kept and objects.writes == []

    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file),
        "--out", str(tmp_path / "final.keyset"), "--allow-empty",
    )
    assert code == 1 and refused["images_blocking"] == {counter: 1}
    assert not (tmp_path / "final.keyset").exists()


async def test_an_object_no_context_opens_is_left_alone_and_blocks(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys, monkeypatch,
):
    """A ciphertext of this keyset that is bound to another response (a copy
    someone moved) is not this response's: it is not rewritten."""
    form_id = signed_form.form_id
    first = await _drawn_response(client, workspace, form_id)
    second = await _drawn_response(client, workspace, form_id)
    one, two = (_key(workspace, form_id, r) for r in (first, second))
    objects.fake.objects[two] = objects.fake.objects[one]
    rotated_file, _, new_key = await rotate(capsys, monkeypatch, tmp_path)

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_resealed"] == 1 and counts["images_unopenable"] == 1
    assert header_key(objects.fake.objects[one]) == new_key  # the copy's source is fine
    assert header_key(objects.fake.objects[two]) == OLD_KEY  # the misplaced one is not touched
    assert objects.writes == [one]

    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file),
        "--out", str(tmp_path / "final.keyset"), "--allow-empty",
    )
    assert code == 1 and refused["images_blocking"] == {"images_stale": 1}


async def test_storage_failures_are_counted_and_never_end_the_run(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys, monkeypatch,
):
    form_id = signed_form.form_id
    first = await _drawn_response(client, workspace, form_id)
    second = await _drawn_response(client, workspace, form_id)
    one, two = (_key(workspace, form_id, r) for r in (first, second))
    rotated_file, _, new_key = await rotate(capsys, monkeypatch, tmp_path)
    objects.unreachable.add(one)  # cannot be looked at

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0
    assert counts["images_storage_errors"] == 1 and counts["images_resealed"] == 1
    assert header_key(objects.fake.objects[two]) == new_key
    assert header_key(objects.fake.objects[one]) == OLD_KEY
    assert counts["records_reencrypted"] == 2  # the rows were rotated all the same
    assert "EndpointConnectionError" not in json.dumps(report)

    # unable to tell where an image stands: drop-old does not guess
    code, refused = await cli(
        capsys, "drop-old", "--keyset-file", str(rotated_file),
        "--out", str(tmp_path / "final.keyset"), "--allow-empty",
    )
    assert code == 1 and refused["images_blocking"] == {"images_storage_errors": 1}

    # a write that fails leaves the object as it was
    objects.unreachable.clear()
    objects.read_only = True
    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_storage_errors"] == 1 and "images_resealed" not in counts
    assert header_key(objects.fake.objects[one]) == OLD_KEY

    # storage back: the next run finishes it
    objects.read_only = False
    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    assert code == 0 and counts_of(report)["images_resealed"] == 1
    assert header_key(objects.fake.objects[one]) == new_key


async def test_an_image_replaced_meanwhile_is_not_overwritten(
    client, workspace, signed_form, objects, rotation_env, tmp_path, capsys, monkeypatch,
):
    form_id, response_id, key = await signed_response(client, workspace, signed_form)
    rotated_file, _, new_key = await rotate(capsys, monkeypatch, tmp_path)
    # a respondent's edit stores a new image between the read and the write
    edited = signatures.seal_image(
        workspace.id, form_id, response_id, "sig", "img-1", _png("edited")
    )
    assert header_key(edited) == new_key
    objects.swap_after_first_read[key] = edited

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["images_changed_concurrently"] == 1
    assert "images_resealed" not in counts and objects.writes == []


async def test_a_response_without_a_drawn_signature_never_touches_the_store(
    client, workspace, signed_form, rotation_env, tmp_path, capsys, monkeypatch,
):
    from tests.app.controllers.test_signature_question_routes import _answers, _submit

    class Untouchable:
        async def read(self, key):  # pragma: no cover - must not run
            raise AssertionError("the file store was used")

        write = read

    monkeypatch.setattr(script, "make_images", lambda: DrawnImages(Untouchable()))
    response = await _submit(
        client, workspace, signed_form.form_id,
        _answers(method="typed", name="Ada Lovelace"),
    )
    assert response.status_code == 200, response.text
    rotated_file, _, _ = await rotate(capsys, monkeypatch, tmp_path)

    code, report = await cli(capsys, "reencrypt", "--keyset-file", str(rotated_file))
    counts = counts_of(report)
    assert code == 0 and counts["records_reencrypted"] == 1
    assert not any(name.startswith("images_") or name == "images_drawn" for name in counts)


# --- the storage adapter -------------------------------------------------------------


class FakeS3Client:
    def __init__(self, objects=None, error=None):
        self.objects = objects or {}
        self.error = error
        self.puts = []

    def _fail(self, code):
        raise ClientError({"Error": {"Code": code, "Message": "x"}}, "Op")

    def head_object(self, Bucket, Key):
        if self.error:
            self._fail(self.error)
        if Key not in self.objects:
            self._fail("404")
        return {"ContentLength": len(self.objects[Key])}

    def get_object(self, Bucket, Key):
        import io

        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, **kwargs):
        self.puts.append(kwargs)
        if self.error:
            self._fail(self.error)


def service_over(client):
    service = AWSS3Service.__new__(AWSS3Service)
    service._s3_client = client
    return service


async def test_read_private_object_tells_gone_from_could_not_look():
    found = service_over(FakeS3Client({"k": b"abc"}))
    assert found.read_private_object("k", 10) == b"abc"
    assert found.read_private_object("other", 10) is None
    with pytest.raises(ValueError):
        found.read_private_object("k", 2)
    # a permission or server error is not "no such object"
    for code in ("403", "AccessDenied", "500", "SlowDown"):
        with pytest.raises(ClientError):
            service_over(FakeS3Client({"k": b"abc"}, error=code)).read_private_object("k", 10)
    assert service_over(FakeS3Client(error="NoSuchKey")).read_private_object("k", 10) is None


async def test_write_private_object_is_private_and_typed():
    client = FakeS3Client()
    service_over(client).write_private_object("k", b"abc", "application/octet-stream")
    (put,) = client.puts
    assert put["Key"] == "k" and put["Body"] == b"abc" and put["ACL"] == "private"
    assert put["ContentType"] == "application/octet-stream"
    with pytest.raises(ClientError):
        service_over(FakeS3Client(error="AccessDenied")).write_private_object("k", b"x", "t")


async def test_s3_objects_map_errors_to_a_type_only():
    objects = S3Objects(service_over(FakeS3Client({"k": b"abc"})))
    assert await objects.read("k") == b"abc" and await objects.read("nope") is None
    with pytest.raises(ObjectStoreError) as failure:
        await S3Objects(service_over(FakeS3Client(error="403"))).read("k")
    assert str(failure.value) == "ClientError"
    with pytest.raises(ObjectStoreError):
        await S3Objects(service_over(FakeS3Client(error="403"))).write("k", b"x")
    big = S3Objects(service_over(FakeS3Client({"k": b"0" * (signatures.SEALED_MAX_BYTES + 1)})))
    with pytest.raises(ObjectTooLarge):
        await big.read("k")


async def test_s3_objects_without_credentials_fail_as_a_storage_error(monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings.aws_settings, "ACCESS_KEY_ID", "")
    with pytest.raises(ObjectStoreError):
        await S3Objects().read("k")
