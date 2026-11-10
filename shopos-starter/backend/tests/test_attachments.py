from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.main import app
from shopos.models import AuditEvent, ProofAttachment, User, UserPermission
from shopos.security import hash_password
from shopos.storage import ObjectHead, S3Storage, StorageUnavailable, get_storage, make_storage

JPEG = b"\xff\xd8\xff" + b"j" * 13


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_promote = False
        self.corrupt_copy = False

    def upload_url(self, key, content_type):
        return f"https://storage.test/upload/{key}?signed=short"

    def download_url(self, key):
        return f"https://storage.test/download/{key}?signed=short"

    def head(self, key):
        stored = self.objects.get(key)
        return ObjectHead(len(stored[0]), stored[1]) if stored else None

    def first_bytes(self, key):
        return self.objects[key][0][:32]

    def promote(self, upload_key, object_key):
        if self.fail_promote:
            raise StorageUnavailable()
        stored = self.objects[upload_key]
        self.objects[object_key] = (b"x" * len(stored[0]), stored[1]) if self.corrupt_copy else stored

    def delete(self, key):
        self.objects.pop(key, None)


@pytest.fixture
def storage(client):
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    try:
        yield fake
    finally:
        app.dependency_overrides.pop(get_storage, None)


def grant(db_engine, user_id, *permissions):
    with Session(db_engine) as db:
        for permission in permissions:
            db.add(UserPermission(user_id=user_id, permission=permission))
        db.commit()


def initiate(client, headers, upload_id=None, size=len(JPEG), content_type="image/jpeg"):
    return client.post(
        "/attachments/proofs/initiate",
        json={"client_upload_id": str(upload_id or uuid4()), "content_type": content_type, "size_bytes": size},
        headers=headers,
    )


def test_upload_retry_complete_and_signed_download(client, db_engine, storage):
    _, employee_id = seed_owner_and_employee(db_engine)
    grant(db_engine, employee_id, "attachments:write", "attachments:read")
    headers = auth_headers(client, "worker", "a-long-worker-password")
    upload_id = uuid4()
    first = initiate(client, headers, upload_id)
    assert first.status_code == 200
    assert first.json()["status"] == "pending"
    assert first.json()["required_headers"] == {"Content-Type": "image/jpeg"}
    assert first.json()["expires_in_seconds"] == 300
    attachment_id = first.json()["id"]
    assert "object_key" not in first.json()

    retry = initiate(client, headers, upload_id)
    assert retry.json()["id"] == attachment_id
    assert initiate(client, headers, upload_id, size=99).status_code == 409
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers).status_code == 409
    assert client.get(f"/attachments/proofs/{attachment_id}/download", headers=headers).status_code == 409

    with Session(db_engine) as db:
        record = db.get(ProofAttachment, attachment_id)
        upload_key, object_key = record.upload_key, record.object_key
    storage.objects[upload_key] = (JPEG[:-1], "image/jpeg")
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers).status_code == 409
    storage.objects[upload_key] = (JPEG, "image/png")
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers).status_code == 409
    storage.objects[upload_key] = (JPEG, "image/jpeg")
    completed = client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers)
    assert completed.status_code == 200
    assert completed.json()["status"] == "ready"
    assert storage.objects[object_key] == (JPEG, "image/jpeg")
    assert upload_key not in storage.objects
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=headers).status_code == 200
    assert initiate(client, headers, upload_id).json()["upload_url"] is None
    assert client.get(f"/attachments/proofs/{attachment_id}", headers=headers).json()["status"] == "ready"
    download = client.get(f"/attachments/proofs/{attachment_id}/download", headers=headers)
    assert download.status_code == 200
    assert object_key in download.json()["download_url"]
    assert download.json()["expires_in_seconds"] == 300
    with Session(db_engine) as db:
        assert db.query(AuditEvent).filter_by(action="proof.initiate").count() == 1
        assert db.query(AuditEvent).filter_by(action="proof.complete").count() == 1
        assert db.query(AuditEvent).filter_by(action="proof.download_url").count() == 1


def test_permissions_and_owner_access(client, db_engine, storage):
    _, employee_id = seed_owner_and_employee(db_engine)
    employee = auth_headers(client, "worker", "a-long-worker-password")
    assert initiate(client, {}).status_code == 401
    assert initiate(client, employee).status_code == 403
    grant(db_engine, employee_id, "attachments:read", "attachments:write")
    first = initiate(client, employee)
    assert first.status_code == 200
    attachment_id = first.json()["id"]

    with Session(db_engine) as db:
        other = User(username="other", display_name="Other", password_hash=hash_password("another-long-password"), role="employee")
        db.add(other)
        db.flush()
        db.add_all([UserPermission(user_id=other.id, permission="attachments:read"), UserPermission(user_id=other.id, permission="attachments:write")])
        db.commit()
    other_headers = auth_headers(client, "other", "another-long-password")
    assert client.get(f"/attachments/proofs/{attachment_id}", headers=other_headers).status_code == 403
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=other_headers).status_code == 403
    assert client.get(f"/attachments/proofs/{attachment_id}/download", headers=other_headers).status_code == 403
    owner = auth_headers(client)
    assert client.get(f"/attachments/proofs/{attachment_id}", headers=owner).status_code == 200


def test_invalid_image_and_storage_failure_can_retry(client, db_engine, storage):
    seed_owner_and_employee(db_engine)
    owner = auth_headers(client)
    assert initiate(client, owner, size=0).status_code == 422
    assert initiate(client, owner, content_type="application/pdf").status_code == 422
    attachment_id = initiate(client, owner).json()["id"]
    with Session(db_engine) as db:
        upload_key = db.get(ProofAttachment, attachment_id).upload_key
    storage.objects[upload_key] = (b"x" * len(JPEG), "image/jpeg")
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=owner).status_code == 422
    storage.objects[upload_key] = (JPEG, "image/jpeg")
    storage.fail_promote = True
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=owner).status_code == 503
    assert client.get(f"/attachments/proofs/{attachment_id}", headers=owner).json()["status"] == "pending"
    storage.fail_promote = False
    storage.corrupt_copy = True
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=owner).status_code == 409
    assert client.get(f"/attachments/proofs/{attachment_id}", headers=owner).json()["status"] == "pending"
    storage.corrupt_copy = False
    assert client.post(f"/attachments/proofs/{attachment_id}/complete", headers=owner).json()["status"] == "ready"


def test_s3_urls_are_short_lived_and_signed():
    storage = S3Storage(
        bucket="synthetic-private-bucket", region="us-east-1", endpoint="https://s3.example.test",
        public_endpoint="https://upload.example.test", access_key="test-key", secret_key="test-secret",
    )
    upload = storage.upload_url("pending/synthetic", "image/jpeg")
    download = storage.download_url("proofs/synthetic")
    assert upload.startswith("https://upload.example.test/synthetic-private-bucket/pending/synthetic?")
    assert "X-Amz-Expires=300" in upload
    assert "X-Amz-Signature=" in upload
    assert "content-type" in upload.lower()
    assert "X-Amz-Expires=300" in download
    assert "X-Amz-Signature=" in download


def test_r2_config_uses_existing_signed_upload_path(monkeypatch):
    monkeypatch.setenv("R2_BUCKET", "shopos-parchi")
    monkeypatch.setenv("R2_ENDPOINT", "https://account.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_REGION", "auto")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "test-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "test-secret")
    make_storage.cache_clear()
    try:
        storage = make_storage()
        url = storage.upload_url("pending/synthetic", "image/jpeg")
        assert url.startswith("https://account.r2.cloudflarestorage.com/shopos-parchi/pending/synthetic?")
        assert "X-Amz-Expires=300" in url
        assert "X-Amz-Signature=" in url
        assert "content-type" in url.lower()
    finally:
        make_storage.cache_clear()
