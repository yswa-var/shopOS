from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from conftest import seed_owner_and_employee
from shopos.models import AuditEvent, ProofAttachment
from shopos.proof_cleanup import cleanup_proofs
from shopos.storage import StorageUnavailable


class FakeStorage:
    def __init__(self):
        self.deleted = []
        self.fail_key = None

    def delete(self, key):
        if key == self.fail_key:
            raise StorageUnavailable()
        self.deleted.append(key)


def proof(user_id, now, *, status, age_days, temp_deleted_at=None):
    return ProofAttachment(
        client_upload_id=uuid4(), uploaded_by=user_id, content_type="image/jpeg", size_bytes=3,
        upload_key=f"pending/{uuid4()}", object_key=f"proofs/{uuid4()}", status=status,
        created_at=now - timedelta(days=age_days),
        ready_at=now - timedelta(days=age_days) if status == "ready" else None,
        temp_deleted_at=temp_deleted_at,
    )


def test_cleanup_is_bounded_and_preserves_ready_proofs(db_engine):
    user_id, _ = seed_owner_and_employee(db_engine)
    now = datetime.now(timezone.utc)
    with Session(db_engine) as db:
        expired = proof(user_id, now, status="pending", age_days=8)
        recent = proof(user_id, now, status="pending", age_days=1)
        ready = proof(user_id, now, status="ready", age_days=2)
        already_clean = proof(user_id, now, status="ready", age_days=2, temp_deleted_at=now - timedelta(days=1))
        db.add_all([expired, recent, ready, already_clean])
        db.commit()
        expired_id, recent_id, ready_id = expired.id, recent.id, ready.id
        expired_keys = {expired.upload_key, expired.object_key}
        ready_upload_key = ready.upload_key

    storage = FakeStorage()
    with Session(db_engine) as db:
        assert cleanup_proofs(db, storage, now=now, limit=1).pending_deleted == 1
        assert db.get(ProofAttachment, expired_id) is None
        assert db.get(ProofAttachment, recent_id) is not None
        assert db.get(ProofAttachment, ready_id).temp_deleted_at is None
        assert set(storage.deleted) == expired_keys
        result = cleanup_proofs(db, storage, now=now, limit=10)
        assert result.temp_deleted == 1
        assert result.pending_deleted == 0
        assert db.get(ProofAttachment, ready_id).temp_deleted_at is not None
        assert ready_upload_key in storage.deleted
        assert db.query(AuditEvent).filter_by(action="proof.expire", target_id=expired_id).count() == 1
        assert cleanup_proofs(db, storage, now=now).temp_deleted == 0


def test_storage_failure_keeps_pending_metadata_for_retry(db_engine):
    user_id, _ = seed_owner_and_employee(db_engine)
    now = datetime.now(timezone.utc)
    with Session(db_engine) as db:
        expired = proof(user_id, now, status="pending", age_days=8)
        db.add(expired)
        db.commit()
        identifier, upload_key = expired.id, expired.upload_key
    storage = FakeStorage()
    storage.fail_key = upload_key
    with Session(db_engine) as db:
        result = cleanup_proofs(db, storage, now=now)
        assert result.failed == 1
        assert db.get(ProofAttachment, identifier) is not None
        storage.fail_key = None
        assert cleanup_proofs(db, storage, now=now).pending_deleted == 1
