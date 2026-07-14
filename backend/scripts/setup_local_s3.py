"""Bootstrap the local S3 bucket (RustFS from docker-compose.local.yml).

Idempotent: creates the bucket and applies the anonymous-read policy for the
PUBLIC prefixes only. Private uploads (``private/*`` — respondent files) stay
unreadable without a presigned URL, exactly like production.

Run:  uv run python scripts/setup_local_s3.py
"""

import json
import os

import boto3
from botocore.exceptions import ClientError

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:9000")
ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "rustfsadmin")
SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "rustfsadmin")
REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = os.environ.get("AWS_BUCKET", "bettercollected")

# RustFS/MinIO ignore per-object ACLs — anonymous read is granted by bucket
# policy, scoped to the prefixes the product treats as public.
PUBLIC_PREFIXES = ["public/*", "media_library/*"]

POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{BUCKET}/{prefix}" for prefix in PUBLIC_PREFIXES],
        }
    ],
}


def main() -> None:
    s3 = boto3.client(
        "s3",
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
        endpoint_url=ENDPOINT,
    )
    try:
        s3.create_bucket(Bucket=BUCKET)
        print(f"created bucket '{BUCKET}'")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code not in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            raise
        print(f"bucket '{BUCKET}' already exists")
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(POLICY))
    print(f"anonymous read enabled for: {', '.join(PUBLIC_PREFIXES)} (private/* stays private)")


if __name__ == "__main__":
    main()
