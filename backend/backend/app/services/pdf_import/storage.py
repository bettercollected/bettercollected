"""Where uploaded originals live: the form's private folder in object storage.

``private/<workspace>/<form>/`` is what deleting a form already removes, so
an original is kept exactly as long as its form (and never publicly served).
"""

from __future__ import annotations

import asyncio
from typing import Dict


def source_key(workspace_id, form_id: str, import_id, extension: str) -> str:
    return f"private/{workspace_id}/{form_id}/imports/{import_id}/source.{extension}"


def artifact_key(source: str, name: str) -> str:
    """A stage's output, stored next to the original (and deleted with the form)."""
    return source.rsplit("/", 1)[0] + f"/{name}"


class ObjectStore:
    async def put(
        self, key: str, data: bytes, content_type: str
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    async def get(self, key: str) -> bytes:  # pragma: no cover
        raise NotImplementedError


class S3ObjectStore(ObjectStore):
    """Private objects in the configured bucket, through the existing S3 service."""

    def __init__(self, aws_service, bucket: str):
        self._aws = aws_service
        self._bucket = bucket

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def upload():
            self._aws._s3.Bucket(self._bucket).put_object(
                Body=data, Key=key, ACL="private", ContentType=content_type
            )

        await asyncio.to_thread(upload)

    async def get(self, key: str) -> bytes:
        def download():
            return self._aws._s3.Object(self._bucket, key).get()["Body"].read()

        return await asyncio.to_thread(download)


class MemoryObjectStore(ObjectStore):
    """For tests."""

    def __init__(self):
        self.objects: Dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def get(self, key: str) -> bytes:
        return self.objects[key]
