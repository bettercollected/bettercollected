import datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException

from backend.config import settings

aws_settings = settings.aws_settings


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
        self._s3_client = boto3.client(
            "s3",
            aws_access_key_id=self._aws_access_key_id,
            aws_secret_access_key=self._aws_secret_access_key,
            region_name="eu-central-1",
            endpoint_url="https://s3.eu-central-1.wasabisys.com",
        )

    async def upload_file_to_s3(
        self,
        file=None,
        key=None,
        previous_image="",
        bucket="bettercollected",
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
        wasabi_domain = "https://s3.eu-central-1.wasabisys.com"
        folder = f"/{bucket}/{folder_name}/{current_time}_{key}"
        if private:
            folder = f"/{bucket}/{folder_name}/{key}"
        return f"{wasabi_domain}{folder}"

    def check_if_key_exists(self, key, bucket="bettercollected"):
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

    def delete_file_from_s3(self, key: str, bucket: str = "bettercollected"):
        try:
            self._s3.Object(bucket, key).delete()
        except ClientError:
            raise HTTPException(404, "INFO: Failed to delete file")

    def delete_folder_from_s3(self, prefix: str, bucket: str = "bettercollected"):
        try:
            for object_summary in self._s3.Bucket(bucket).objects.filter(Prefix=prefix):
                object_summary.delete()
        except ClientError:
            return

    def generate_presigned_url(self, key: str, bucket="bettercollected"):
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
