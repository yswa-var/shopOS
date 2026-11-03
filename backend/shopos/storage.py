import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

SIGNED_URL_SECONDS = 300


class StorageUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ObjectHead:
    size_bytes: int
    content_type: str


class S3Storage:
    def __init__(self, *, bucket: str, region: str, endpoint: str | None, public_endpoint: str | None, access_key: str | None, secret_key: str | None):
        self.bucket = bucket
        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        config = Config(signature_version="s3v4", s3={"addressing_style": "path"})
        self.internal = session.client("s3", endpoint_url=endpoint, config=config)
        self.public = session.client("s3", endpoint_url=public_endpoint or endpoint, config=config)

    def upload_url(self, key: str, content_type: str) -> str:
        try:
            return self.public.generate_presigned_url(
                "put_object", Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type}, ExpiresIn=SIGNED_URL_SECONDS, HttpMethod="PUT"
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable from exc

    def download_url(self, key: str) -> str:
        try:
            return self.public.generate_presigned_url(
                "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=SIGNED_URL_SECONDS, HttpMethod="GET"
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable from exc

    def head(self, key: str) -> ObjectHead | None:
        try:
            metadata = self.internal.head_object(Bucket=self.bucket, Key=key)
            return ObjectHead(size_bytes=metadata["ContentLength"], content_type=metadata["ContentType"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise StorageUnavailable from exc
        except BotoCoreError as exc:
            raise StorageUnavailable from exc

    def first_bytes(self, key: str) -> bytes:
        try:
            response = self.internal.get_object(Bucket=self.bucket, Key=key, Range="bytes=0-31")
            body = response["Body"]
            try:
                return body.read(32)
            finally:
                body.close()
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable from exc

    def promote(self, upload_key: str, object_key: str) -> None:
        # Only the temporary key is writable by a signed PUT; saved proof points at the copied key.
        try:
            self.internal.copy_object(Bucket=self.bucket, Key=object_key, CopySource={"Bucket": self.bucket, "Key": upload_key})
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable from exc

    def delete(self, key: str) -> None:
        try:
            self.internal.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise StorageUnavailable from exc


@lru_cache(maxsize=1)
def make_storage() -> S3Storage:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        raise RuntimeError("S3_BUCKET is required")
    access_key = os.getenv("S3_ACCESS_KEY_ID") or None
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY") or None
    if bool(access_key) != bool(secret_key):
        raise RuntimeError("Both S3 access key and secret must be set together")
    return S3Storage(
        bucket=bucket,
        region=os.getenv("S3_REGION", "us-east-1"),
        endpoint=os.getenv("S3_ENDPOINT_URL") or None,
        public_endpoint=os.getenv("S3_PUBLIC_ENDPOINT_URL") or None,
        access_key=access_key,
        secret_key=secret_key,
    )


def get_storage() -> S3Storage:
    try:
        return make_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc
