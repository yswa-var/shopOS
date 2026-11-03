from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shopos.db import make_engine
from shopos.auth import router as auth_router, Db, require_owner
from shopos.models import AuditEvent
from sqlalchemy import select


app = FastAPI(title="ShopOS API", version="0.1.0")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness must remain available while the database is starting."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        with make_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ready"}


@app.get("/audit/events", dependencies=[Depends(require_owner)])
def audit_events(db: Db) -> list[dict[str, str | None]]:
    """The first protected operation establishes the owner-only audit boundary."""
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)).all()
    return [{"id": str(event.id), "action": event.action, "actor_id": str(event.actor_id) if event.actor_id else None} for event in events]
