"""Persistent bill-draft lifecycle and merge operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from shopos.db.connection import connect
from shopos.db.migrations import migrate


DraftState = Literal["COLLECTING", "AWAITING_CONFIRMATION", "COMMITTING"]
VALID_STATES = frozenset({"COLLECTING", "AWAITING_CONFIRMATION", "COMMITTING"})


class DraftNotFoundError(LookupError):
    """Raised when an operation requires a draft that does not exist."""


class DraftRecord:
    """A persisted draft and its JSON payload."""

    __slots__ = (
        "draft_id",
        "telegram_user_id",
        "state",
        "draft_data",
        "updated_at",
        "expires_at",
    )

    def __init__(
        self,
        *,
        draft_id: str,
        telegram_user_id: int,
        state: DraftState,
        draft_data: dict[str, Any],
        updated_at: str,
        expires_at: str,
    ) -> None:
        self.draft_id = draft_id
        self.telegram_user_id = telegram_user_id
        self.state = state
        self.draft_data = draft_data
        self.updated_at = updated_at
        self.expires_at = expires_at


def merge_draft_data(
    current: Mapping[str, Any], updates: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge non-null updates without discarding unrelated draft fields."""

    merged = dict(current)
    for key, value in updates.items():
        if value is None:
            continue
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = merge_draft_data(existing, value)
        else:
            merged[key] = value
    return merged


class DraftService:
    """Own the persistent lifecycle of one active draft per Telegram user."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        business_timezone: str = "Asia/Kolkata",
        ttl: timedelta = timedelta(hours=24),
    ) -> None:
        self.database_path = Path(database_path)
        self._timezone = ZoneInfo(business_timezone)
        if ttl <= timedelta(0):
            raise ValueError("draft TTL must be positive")
        self._ttl = ttl

    def _now(self) -> datetime:
        return datetime.now(self._timezone)

    @staticmethod
    def _record_from_row(row: Any) -> DraftRecord:
        state = row["state"]
        if state not in VALID_STATES:
            raise ValueError(f"invalid persisted draft state: {state}")
        data = json.loads(row["draft_json"])
        if not isinstance(data, dict):
            raise ValueError("draft_json must contain a JSON object")
        return DraftRecord(
            draft_id=row["draft_id"],
            telegram_user_id=row["telegram_user_id"],
            state=state,
            draft_data=data,
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )

    async def start_or_resume(self, telegram_user_id: int) -> tuple[DraftRecord, bool]:
        """Return the active draft, creating it when the user has none."""

        await migrate(self.database_path)
        now = self._now()
        now_text = now.isoformat()
        expires_text = (now + self._ttl).isoformat()
        async with connect(self.database_path) as connection:
            await connection.execute("BEGIN IMMEDIATE")
            try:
                cursor = await connection.execute(
                    "SELECT * FROM bill_drafts WHERE telegram_user_id = ?",
                    (telegram_user_id,),
                )
                row = await cursor.fetchone()
                if row is not None:
                    if row["expires_at"] > now_text:
                        await connection.commit()
                        return self._record_from_row(row), True
                    await connection.execute(
                        "DELETE FROM bill_drafts WHERE telegram_user_id = ?",
                        (telegram_user_id,),
                    )

                draft_id = str(uuid4())
                draft_data = self._new_draft_data(now)
                await connection.execute(
                    """
                    INSERT INTO bill_drafts(
                        draft_id, telegram_user_id, state, draft_json,
                        updated_at, expires_at
                    ) VALUES (?, ?, 'COLLECTING', ?, ?, ?)
                    """,
                    (
                        draft_id,
                        telegram_user_id,
                        json.dumps(draft_data, separators=(",", ":"), sort_keys=True),
                        now_text,
                        expires_text,
                    ),
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise

        return DraftRecord(
            draft_id=draft_id,
            telegram_user_id=telegram_user_id,
            state="COLLECTING",
            draft_data=draft_data,
            updated_at=now_text,
            expires_at=expires_text,
        ), False

    @staticmethod
    def _new_draft_data(now: datetime) -> dict[str, Any]:
        return {
            "invoice_number": f"INV-{now:%y}-{uuid4().hex[:8].upper()}",
            "proof": None,
            "vendor_id": None,
            "account_id": None,
            "items": [],
            "tax": "0.00",
            "charges": "0.00",
            "paid_balance": "0.00",
            "due_at": None,
        }

    async def get(self, telegram_user_id: int) -> DraftRecord | None:
        await migrate(self.database_path)
        async with connect(self.database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM bill_drafts WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            row = await cursor.fetchone()
        return self._record_from_row(row) if row is not None else None

    async def merge(
        self,
        telegram_user_id: int,
        updates: Mapping[str, Any],
        *,
        state: DraftState | None = None,
    ) -> DraftRecord:
        """Merge updates into the active draft and refresh its expiry."""

        if state is not None and state not in VALID_STATES:
            raise ValueError(f"invalid draft state: {state}")
        existing = await self.get(telegram_user_id)
        if existing is None:
            raise DraftNotFoundError(telegram_user_id)

        now = self._now()
        merged = merge_draft_data(existing.draft_data, updates)
        next_state = state or existing.state
        expires_text = (now + self._ttl).isoformat()
        async with connect(self.database_path) as connection:
            await connection.execute("BEGIN")
            try:
                await connection.execute(
                    """
                    UPDATE bill_drafts
                    SET state = ?, draft_json = ?, updated_at = ?, expires_at = ?
                    WHERE telegram_user_id = ?
                    """,
                    (
                        next_state,
                        json.dumps(merged, separators=(",", ":"), sort_keys=True),
                        now.isoformat(),
                        expires_text,
                        telegram_user_id,
                    ),
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        return DraftRecord(
            draft_id=existing.draft_id,
            telegram_user_id=telegram_user_id,
            state=next_state,
            draft_data=merged,
            updated_at=now.isoformat(),
            expires_at=expires_text,
        )

    async def cancel(self, telegram_user_id: int) -> bool:
        """Delete the active draft and return whether one existed."""

        await migrate(self.database_path)
        async with connect(self.database_path) as connection:
            await connection.execute("BEGIN")
            try:
                cursor = await connection.execute(
                    "DELETE FROM bill_drafts WHERE telegram_user_id = ?",
                    (telegram_user_id,),
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        return cursor.rowcount == 1

    async def cleanup_expired(self, *, now: datetime | None = None) -> int:
        """Delete expired drafts except those currently COMMITTING."""

        await migrate(self.database_path)
        current = now.astimezone(self._timezone) if now else self._now()
        async with connect(self.database_path) as connection:
            await connection.execute("BEGIN")
            try:
                cursor = await connection.execute(
                    """
                    DELETE FROM bill_drafts
                    WHERE expires_at <= ? AND state != 'COMMITTING'
                    """,
                    (current.isoformat(),),
                )
                await connection.commit()
            except Exception:
                await connection.rollback()
                raise
        return cursor.rowcount

