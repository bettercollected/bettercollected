"""An in-memory stand-in for the two boto3 objects the storage adapter
(``backend/app/services/aws_service.py``) talks to.

The adapter keeps its own logic (keys, public URLs, which errors it maps); only
the calls that would leave the process are replaced: ``boto3.resource("s3")``
(``Bucket(...).put_object``, ``.objects.filter``, ``Object(...).delete``) and
``boto3.client("s3")`` (``head_object``, ``copy_object``, ``get_object``,
``generate_presigned_url``). Without it a test that deletes a response (or a
form, a workspace, a media file) makes boto3 look for credentials and try the
network: about 0.3 s on a quiet machine, more than a second on CI.

``tests/conftest.py`` installs it for every test (``in_memory_storage``);
``@pytest.mark.real_storage_client`` leaves the real objects in place for a
test that drives them itself.
"""

import hashlib
from typing import Any, Dict, Iterator, Optional

from botocore.exceptions import ClientError


def _missing(operation: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, operation
    )


def etag_of(data: bytes) -> str:
    """The ETag S3 gives a single-part object: the quoted MD5 of its bytes."""
    return '"' + hashlib.md5(data).hexdigest() + '"'  # noqa: S324 (not a secret)


def _precondition_failed(operation: str) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": "PreconditionFailed", "Message": "At least one of the pre-conditions you specified did not hold"},
            "ResponseMetadata": {"HTTPStatusCode": 412},
        },
        operation,
    )


class FakeStore:
    """bucket -> key -> (bytes, extra arguments of the put)."""

    def __init__(self) -> None:
        self.objects: Dict[str, Dict[str, tuple]] = {}

    def put(self, bucket: str, key: str, body: Any, **extra: Any) -> None:
        if hasattr(body, "read"):
            body = body.read()
        data = body.encode() if isinstance(body, str) else bytes(body or b"")
        self.objects.setdefault(bucket, {})[key] = (data, extra)

    def keys(self, bucket: str) -> list:
        return sorted(self.objects.get(bucket, {}))

    def remove(self, bucket: str, key: str) -> None:
        self.objects.get(bucket, {}).pop(key, None)


class _Body:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.closed = False

    def read(self, amount: Optional[int] = None) -> bytes:
        return self._data if amount is None else self._data[:amount]

    def close(self) -> None:
        self.closed = True


class _Object:
    def __init__(self, store: FakeStore, bucket: str, key: str) -> None:
        self._store, self._bucket, self.key = store, bucket, key

    def get(self, **_: Any) -> dict:
        found = self._store.objects.get(self._bucket, {}).get(self.key)
        if found is None:
            raise _missing("GetObject")
        data, _extra = found
        return {"Body": _Body(data), "ContentLength": len(data), "ETag": etag_of(data)}

    def delete(self) -> dict:
        self._store.remove(self._bucket, self.key)
        return {}


class _Objects:
    def __init__(self, store: FakeStore, bucket: str) -> None:
        self._store, self._bucket = store, bucket

    def filter(self, Prefix: str = "") -> Iterator[_Object]:
        # a snapshot: a caller deleting while it iterates is fine
        for key in [k for k in self._store.keys(self._bucket) if k.startswith(Prefix)]:
            yield _Object(self._store, self._bucket, key)


class _Bucket:
    def __init__(self, store: FakeStore, name: str) -> None:
        self._store, self.name = store, name
        self.objects = _Objects(store, name)

    def put_object(self, Body: Any = b"", Key: str = "", **extra: Any) -> dict:
        self._store.put(self.name, Key, Body, **extra)
        return {}


class FakeResource:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    def Bucket(self, name: str) -> _Bucket:  # noqa: N802 (boto3's spelling)
        return _Bucket(self._store, name)

    def Object(self, bucket: str, key: str) -> _Object:  # noqa: N802
        return _Object(self._store, bucket, key)


class FakeClient:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    def _get(self, bucket: str, key: str, operation: str) -> tuple:
        found = self._store.objects.get(bucket, {}).get(key)
        if found is None:
            raise _missing(operation)
        return found

    def head_object(self, Bucket: str, Key: str, **_: Any) -> dict:
        data, _extra = self._get(Bucket, Key, "HeadObject")
        return {"ContentLength": len(data), "ETag": etag_of(data)}

    def get_object(self, Bucket: str, Key: str, **_: Any) -> dict:
        data, _extra = self._get(Bucket, Key, "GetObject")
        return {"Body": _Body(data), "ContentLength": len(data), "ETag": etag_of(data)}

    def put_object(self, Bucket: str, Key: str, Body: Any = b"", IfMatch: Optional[str] = None, **extra: Any) -> dict:
        """``IfMatch``: the object must exist with that ETag (404 NoSuchKey
        when it is gone, 412 PreconditionFailed when it changed), as S3 does."""
        if IfMatch is not None:
            found = self._store.objects.get(Bucket, {}).get(Key)
            if found is None:
                raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}, "PutObject")
            if etag_of(found[0]) != IfMatch:
                raise _precondition_failed("PutObject")
        self._store.put(Bucket, Key, Body, **extra)
        return {"ETag": etag_of(self._store.objects[Bucket][Key][0])}

    def copy_object(self, Bucket: str, Key: str, CopySource: dict, **extra: Any) -> dict:
        data, _extra = self._get(CopySource["Bucket"], CopySource["Key"], "CopyObject")
        self._store.put(Bucket, Key, data, **extra)
        return {}

    def generate_presigned_url(
        self, ClientMethod: str, Params: Optional[dict] = None, ExpiresIn: int = 3600, **_: Any
    ) -> str:
        params = dict(Params or {})
        return f"https://storage.test/{params.pop('Bucket', '')}/{params.pop('Key', '')}?expires={ExpiresIn}"
