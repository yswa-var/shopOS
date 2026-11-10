from uuid import UUID

from sqlalchemy.orm import Session

from shopos.models import AuditEvent


def record_event(db: Session, *, actor_id: UUID | None, action: str, target_type: str, target_id: UUID | None) -> None:
    """Write inside the caller's transaction so state changes and audit stay together."""
    db.add(AuditEvent(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id))
