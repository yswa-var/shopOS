"""Optional local S3 integration check; run with SHOPOS_TEST_S3=1."""
import base64
import os
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.models import ProofAttachment
from shopos.storage import make_storage

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/hioAAAAASUVORK5CYII=")


def test_real_signed_put_copy_and_get(client, db_engine):
    if os.getenv("SHOPOS_TEST_S3") != "1":
        pytest.skip("Set SHOPOS_TEST_S3=1 with a local S3 test bucket")
    seed_owner_and_employee(db_engine)
    headers = auth_headers(client)
    response = client.post(
        "/attachments/proofs/initiate",
        json={"client_upload_id": str(uuid4()), "content_type": "image/png", "size_bytes": len(PNG)},
        headers=headers,
    )
    assert response.status_code == 200
    attachment_id = response.json()["id"]
    storage = make_storage()
    try:
        put = httpx.put(response.json()["upload_url"], content=PNG, headers=response.json()["required_headers"])
        assert put.status_code in {200, 204}
        complete = client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers)
        assert complete.status_code == 200
        assert complete.json()["status"] == "ready"
        signed_url = client.get(f"/attachments/proofs/{attachment_id}/download", headers=headers).json()["download_url"]
        assert httpx.get(signed_url).content == PNG
        with Session(db_engine) as db:
            object_key = db.get(ProofAttachment, attachment_id).object_key
        direct_url = f"{os.environ['S3_ENDPOINT_URL'].rstrip('/')}/{storage.bucket}/{object_key}"
        assert httpx.get(direct_url).status_code == 403
    finally:
        with Session(db_engine) as db:
            record = db.get(ProofAttachment, attachment_id)
            storage.internal.delete_object(Bucket=storage.bucket, Key=record.upload_key)
            storage.internal.delete_object(Bucket=storage.bucket, Key=record.object_key)
