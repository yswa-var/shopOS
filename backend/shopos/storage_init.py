"""Prepare local SeaweedFS credentials and a private bucket; never run during deploy."""
import json
import os
import sys
import time
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from shopos.storage import S3Storage

CONFIG_PATH = Path(__file__).resolve().parents[2] / ".local" / "seaweedfs-s3.json"


def write_local_config() -> None:
    access_key = os.environ.get("S3_ACCESS_KEY_ID")
    secret_key = os.environ.get("S3_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("Local storage requires S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY")
    data = {"identities": [{"name": "shopos-local", "credentials": [{"accessKey": access_key, "secretKey": secret_key}], "actions": ["Admin", "Read", "List", "Write"]}]}
    CONFIG_PATH.parent.mkdir(mode=0o700, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data))
    CONFIG_PATH.chmod(0o600)
    print("Local S3 identity configured")


def create_bucket() -> None:
    if not os.getenv("S3_ENDPOINT_URL"):
        raise RuntimeError("Local bucket setup requires S3_ENDPOINT_URL")
    # This command only prepares SeaweedFS, even when the API is set to R2.
    storage = S3Storage(
        bucket=os.environ["S3_BUCKET"], region=os.getenv("S3_REGION", "us-east-1"),
        endpoint=os.environ["S3_ENDPOINT_URL"], public_endpoint=os.getenv("S3_PUBLIC_ENDPOINT_URL"),
        access_key=os.environ["S3_ACCESS_KEY_ID"], secret_key=os.environ["S3_SECRET_ACCESS_KEY"],
    )
    for attempt in range(30):
        try:
            storage.internal.head_bucket(Bucket=storage.bucket)
            print("Private bucket ready")
            return
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchBucket", "NotFound"}:
                parameters = {"Bucket": storage.bucket}
                region = storage.internal.meta.region_name
                if region != "us-east-1":
                    parameters["CreateBucketConfiguration"] = {"LocationConstraint": region}
                storage.internal.create_bucket(**parameters)
                print("Private bucket created")
                return
            raise
        except BotoCoreError:
            if attempt == 29:
                raise
            time.sleep(1)


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"config", "bucket"}:
        raise SystemExit("Usage: python -m shopos.storage_init [config|bucket]")
    if sys.argv[1] == "config":
        write_local_config()
    else:
        create_bucket()


if __name__ == "__main__":
    main()
