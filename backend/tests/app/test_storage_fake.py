"""The in-memory storage the test suite installs for every test
(tests/app/storage_fake.py), used through the real adapter the way the
application uses it: a conditional write, the body's close, the resource's
object read and the ACL a put carries."""

import pytest
from botocore.exceptions import ClientError

from backend.app.container import container
from backend.config import settings

BUCKET = settings.aws_settings.BUCKET


def test_a_private_object_is_written_read_back_and_replaced_only_over_its_version(in_memory_storage):
    aws = container.aws_service()
    aws.write_private_object("private/w/f/r/a.bin", b"one", "image/png")
    # ACL and content type of the put are recorded
    _data, extra = in_memory_storage.objects[BUCKET]["private/w/f/r/a.bin"]
    assert extra["ACL"] == "private" and extra["ContentType"] == "image/png"

    found = aws.read_private_object_tagged("private/w/f/r/a.bin", 100)
    assert found is not None and found[0] == b"one" and found[1]
    etag = found[1]

    aws.write_private_object("private/w/f/r/a.bin", b"two", "image/png", if_match=etag)
    assert aws.read_private_object("private/w/f/r/a.bin", 100) == b"two"

    # the old version no longer matches: the same precondition error S3 gives
    with pytest.raises(ClientError) as stale:
        aws.write_private_object("private/w/f/r/a.bin", b"three", "image/png", if_match=etag)
    assert stale.value.response["Error"]["Code"] == "PreconditionFailed"
    assert stale.value.response["ResponseMetadata"]["HTTPStatusCode"] == 412
    assert aws.read_private_object("private/w/f/r/a.bin", 100) == b"two"

    # a conditional write over an object that is gone is a 404, not a create
    aws.delete_file_from_s3("private/w/f/r/a.bin")
    with pytest.raises(ClientError) as gone:
        aws.write_private_object("private/w/f/r/a.bin", b"four", "image/png", if_match=etag)
    assert gone.value.response["Error"]["Code"] == "NoSuchKey"
    assert aws.read_private_object("private/w/f/r/a.bin", 100) is None


def test_the_body_is_closed_after_a_read(in_memory_storage, monkeypatch):
    aws = container.aws_service()
    aws.write_private_object("private/k", b"x", "image/png")
    bodies = []
    real = aws._s3_client.get_object

    def spy(**kwargs):
        got = real(**kwargs)
        bodies.append(got["Body"])
        return got

    monkeypatch.setattr(aws._s3_client, "get_object", spy)
    assert aws.read_private_object_tagged("private/k", 10)[0] == b"x"
    assert len(bodies) == 1 and bodies[0].closed


def test_the_resource_object_reads_what_was_put_and_misses_what_is_gone(in_memory_storage):
    aws = container.aws_service()
    aws._s3.Bucket(BUCKET).put_object(Body=b"hello", Key="public/x.txt", ACL="public-read")
    assert in_memory_storage.objects[BUCKET]["public/x.txt"][1]["ACL"] == "public-read"
    got = aws._s3.Object(BUCKET, "public/x.txt").get()
    assert got["Body"].read() == b"hello" and got["ContentLength"] == 5
    aws._s3.Object(BUCKET, "public/x.txt").delete()
    with pytest.raises(ClientError):
        aws._s3.Object(BUCKET, "public/x.txt").get()
