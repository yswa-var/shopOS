from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from shopos.db import make_engine

app = FastAPI(title="ShopOS API", version="0.1.0")


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
