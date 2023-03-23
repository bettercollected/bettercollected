import datetime

import boto3

from botocore.exceptions import ClientError

from fastapi import HTTPException


class AWSS3Service:
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str):
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._s3 = boto3.resource(
            "s3",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            region_name="eu-central-1",
            endpoint_url="https://s3.eu-central-1.wasabisys.com",
        )

    async def upload_file_to_s3(
        self, file_name=None, key=None, previous_image="", bucket="bettercollected"
    ):
        # If S3 object_name was not specified, use file_name
        if (key is None) or (bucket is None):
            return None
        # Upload the file
        try:
            current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            self._s3.Bucket(bucket).put_object(
                Body=file_name, Key=f"public/{current_time}_{key}", ACL="public-read"
            )
            if previous_image:
                # extract previous key from the link
                previous_key = previous_image[previous_image.find("public") :]
                # remove image from wasabi
                self._s3.Object(bucket, previous_key).delete()
        except ClientError:
            raise HTTPException(550, "INFO: Failed to upload image")
        except Exception:
            raise HTTPException(550, "INFO: Failed to upload image")
        wasabi_domain = "https://s3.eu-central-1.wasabisys.com"
        folder = f"/{bucket}/public/{current_time}_{key}"
        return f"{wasabi_domain}{folder}"
