"""Bounded cleanup of temporary proof objects; run on a schedule or manually."""
import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from shopos.audit import record_event
from shopos.db import make_engine
from shopos.models import ProofAttachment
from shopos.storage import S3Storage, StorageUnavailable, make_storage


@dataclass(frozen=True)
class CleanupResult:
    pending_deleted: int = 0
    temp_deleted: int = 0
    failed: int = 0


def cleanup_proofs(db: Session, storage: S3Storage, *, now: datetime, pending_days: int = 7, limit: int = 100) -> CleanupResult:
    if pending_days < 1 or not 1 <= limit <= 1000:
        raise ValueError("pending_days must be positive and limit must be 1–1000")
    pending = db.scalars(
        select(ProofAttachment).where(ProofAttachment.status == "pending", ProofAttachment.created_at < now - timedelta(days=pending_days))
        .order_by(ProofAttachment.created_at).limit(limit).with_for_update(skip_locked=True)
    ).all()
    ready = db.scalars(
        select(ProofAttachment).where(ProofAttachment.status == "ready", ProofAttachment.temp_deleted_at.is_(None), ProofAttachment.ready_at < now - timedelta(hours=1))
        .order_by(ProofAttachment.ready_at).limit(limit - len(pending)).with_for_update(skip_locked=True)
    ).all() if len(pending) < limit else []
    pending_deleted = temp_deleted = failed = 0
    for proof in pending:
        try:
            # A failed completion may have copied a final object before the DB status changed.
            storage.delete(proof.upload_key)
            storage.delete(proof.object_key)
        except StorageUnavailable:
            failed += 1
            continue
        record_event(db, actor_id=None, action="proof.expire", target_type="proof", target_id=proof.id)
        db.delete(proof)
        pending_deleted += 1
    for proof in ready:
        try:
            storage.delete(proof.upload_key)
        except StorageUnavailable:
            failed += 1
            continue
        proof.temp_deleted_at = now
        temp_deleted += 1
    db.commit()
    return CleanupResult(pending_deleted, temp_deleted, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove abandoned proof uploads and leftover temporary objects")
    parser.add_argument("--pending-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    engine = make_engine()
    try:
        with Session(engine) as db:
            result = cleanup_proofs(db, make_storage(), now=datetime.now(timezone.utc), pending_days=args.pending_days, limit=args.limit)
        print(f"Pending removed: {result.pending_deleted}; ready temporary objects removed: {result.temp_deleted}; failures: {result.failed}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
