import datetime
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import HTTPException

from backend.config import settings

aws_settings = settings.aws_settings


class AWSS3Service:
    """Works against any S3-compatible store — Wasabi in production,
    RustFS/MinIO locally. Endpoint/region/bucket come from AWS_* settings."""

    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str):
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        # SigV4 + path-style addressing work across every S3-compatible
        # store we target (Wasabi, RustFS, MinIO). Without the explicit
        # signature version, presigned URLs 403 on RustFS.
        client_config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
        self._s3 = boto3.resource(
            "s3",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            region_name=aws_settings.REGION,
            endpoint_url=aws_settings.ENDPOINT_URL,
            config=client_config,
        )
        self._s3_client = boto3.client(
            "s3",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            region_name=aws_settings.REGION,
            endpoint_url=aws_settings.ENDPOINT_URL,
            config=client_config,
        )

    async def upload_file_to_s3(
        self,
        file=None,
        key=None,
        previous_image="",
        bucket=aws_settings.BUCKET,
        private=False,
        folder_name="public",
    ):
        # If S3 object_name was not specified, use file_name
        if (key is None) or (bucket is None):
            return None
        # Upload the file
        try:
            current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            if private:
                self._s3.Bucket(bucket).put_object(
                    Body=file, Key=f"{folder_name}/{key}", ACL="private"
                )
            else:
                self._s3.Bucket(bucket).put_object(
                    Body=file,
                    Key=f"{folder_name}/{current_time}_{key}",
                    ACL="public-read",
                )
            if previous_image:
                # extract previous key from the link
                previous_key = previous_image[previous_image.find("public") :]
                # remove image from wasabi
                self._s3.Object(bucket, previous_key).delete()
        except ClientError:
            raise HTTPException(550, "INFO: Failed to upload image")
        except Exception as other_exception:
            print("Other Exception:", other_exception)
            raise HTTPException(550, "INFO: Failed to upload image")
        folder = f"/{bucket}/{folder_name}/{current_time}_{key}"
        if private:
            folder = f"/{bucket}/{folder_name}/{key}"
        return f"{aws_settings.public_base_url}{folder}"

    # -- public objects addressed by their URL --------------------------------
    # Images a respondent page shows (form logos) live under ``public/`` in our
    # own bucket and are read through ``public_base_url``. These helpers take
    # and return those URLs, and refuse any URL that is not one of ours.

    @staticmethod
    def public_key_of(url: Optional[str], bucket: str = aws_settings.BUCKET):
        """The object key of a public URL in our own storage, else None."""
        if not url or not isinstance(url, str):
            return None
        base = (aws_settings.public_base_url or "").rstrip("/")
        if not base:
            return None
        prefix = f"{base}/{bucket}/"
        if not url.startswith(prefix):
            return None
        key = url[len(prefix) :]
        if (
            not key.startswith("public/")
            or ".." in key.split("/")
            or any(c in key for c in "?#\\")
        ):
            return None
        return key

    @staticmethod
    def public_url_of(key: str, bucket: str = aws_settings.BUCKET) -> str:
        return f"{aws_settings.public_base_url.rstrip('/')}/{bucket}/{key}"

    def put_public_object(
        self, body: bytes, key: str, content_type: str, bucket=aws_settings.BUCKET
    ) -> str:
        """Store ``body`` under ``key`` (in ``public/``), readable by anyone,
        with its real content type; returns its public URL."""
        if not key.startswith("public/"):
            raise ValueError("public objects live under public/")
        try:
            self._s3.Bucket(bucket).put_object(
                Body=body,
                Key=key,
                ACL="public-read",
                ContentType=content_type,
                CacheControl="public, max-age=31536000, immutable",
            )
        except ClientError:
            raise HTTPException(550, "INFO: Failed to upload image")
        return self.public_url_of(key, bucket)

    def public_object_exists(self, key: str, bucket=aws_settings.BUCKET) -> bool:
        """Whether one of our public objects is stored under ``key``; False
        when it isn't, or the store can't say (the caller then makes it)."""
        if not key.startswith("public/"):
            return False
        try:
            self._s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError:
            return False
        return True

    def copy_public_object(
        self, source_url: str, key: str, bucket=aws_settings.BUCKET
    ) -> Optional[str]:
        """Copy one of our public objects to ``key``; None when the source is
        not ours or no longer exists."""
        source_key = self.public_key_of(source_url, bucket)
        if not source_key or not key.startswith("public/"):
            return None
        try:
            self._s3_client.copy_object(
                Bucket=bucket,
                Key=key,
                CopySource={"Bucket": bucket, "Key": source_key},
                ACL="public-read",
                MetadataDirective="COPY",
            )
        except ClientError:
            return None
        return self.public_url_of(key, bucket)

    def delete_public_object(self, url: str, bucket=aws_settings.BUCKET) -> bool:
        """Delete one of our public objects by its URL; False when the URL is
        not ours or the store refused."""
        key = self.public_key_of(url, bucket)
        if not key:
            return False
        try:
            self._s3.Object(bucket, key).delete()
        except ClientError:
            return False
        return True

    def check_if_key_exists(self, key, bucket=aws_settings.BUCKET):
        try:
            objs = list(self._s3.Bucket(bucket).objects.filter(Prefix=key))
            if len(objs) > 0:
                return True
            else:
                return False
        except ClientError as e:
            raise HTTPException(404, e.response["Error"]["Message"])

    """
        key : path to your file
    """

    def delete_file_from_s3(self, key: str, bucket: str = aws_settings.BUCKET):
        try:
            self._s3.Object(bucket, key).delete()
        except ClientError:
            raise HTTPException(404, "INFO: Failed to delete file")

    def delete_folder_from_s3(self, prefix: str, bucket: str = aws_settings.BUCKET):
        try:
            for object_summary in self._s3.Bucket(bucket).objects.filter(Prefix=prefix):
                object_summary.delete()
        except ClientError:
            return

    def read_object(
        self, key: str, max_bytes: int, bucket=aws_settings.BUCKET
    ) -> Optional[bytes]:
        """The object's bytes, ``None`` when there is no such object. Raises
        ``ValueError`` (naming no content) when it is larger than ``max_bytes``;
        blocking, so async callers run it in a thread."""
        try:
            head = self._s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError:
            return None
        if int(head.get("ContentLength", 0)) > max_bytes:
            raise ValueError("object too large")
        try:
            body = self._s3_client.get_object(Bucket=bucket, Key=key)["Body"]
            data = body.read(max_bytes + 1)
        except ClientError:
            return None
        if len(data) > max_bytes:
            raise ValueError("object too large")
        return data

    def generate_presigned_url(self, key: str, bucket=aws_settings.BUCKET):
        try:
            presigned_url = self._s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=aws_settings.PRE_SIGNED_URL_EXPIRY * 60,
            )
            return presigned_url
        except ClientError as e:
            print(e)
            raise HTTPException(500, "INFO: Failed to generate pre-signed url")
