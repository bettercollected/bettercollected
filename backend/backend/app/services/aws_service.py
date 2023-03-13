import datetime

import boto3
import loguru
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
        self, file_name=None, key=None, previousImage="", bucket="bettercollected"
    ):
        # If S3 object_name was not specified, use file_name
        if (key is None) or (bucket is None):
            return None
        # Upload the file
        try:
            current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            response = self._s3.Bucket(bucket).put_object(
                Body=file_name, Key=f"public/{current_time}_{key}", ACL="public-read"
            )
            if previousImage:
                # extract previous key from the link
                previous_key = previousImage[previousImage.find("public") :]
                # remove image from wasabi
                delete_response = self._s3.Object(bucket, previous_key).delete()
        except ClientError as e:
            raise HTTPException(550, "INFO: Failed to upload image")
        except Exception as e:
            raise HTTPException(550, "INFO: Failed to upload image")
        return f"https://s3.eu-central-1.wasabisys.com/{bucket}/public/{current_time}_{key}"
