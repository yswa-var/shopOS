from datetime import datetime, timedelta

import pytest

from shopos.db.connection import connect
from shopos.services.draft_service import DraftService


@pytest.mark.asyncio
async def test_start_or_resume_preserves_existing_draft(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    service = DraftService(database_path)

    first, resumed = await service.start_or_resume(12)
    assert resumed is False
    updated = await service.merge(
        12,
        {"vendor_name": "ABC Traders", "items": [{"name": "Haldi"}]},
    )

    second, resumed = await service.start_or_resume(12)

    assert resumed is True
    assert second.draft_id == first.draft_id
    assert second.draft_data["vendor_name"] == "ABC Traders"
    assert second.draft_data["items"] == [{"name": "Haldi"}]
    assert second.updated_at == updated.updated_at


@pytest.mark.asyncio
async def test_draft_survives_service_recreation(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    service = DraftService(database_path)
    created, _ = await service.start_or_resume(12)
    await service.merge(12, {"account_name": "Firm A"})

    restarted_service = DraftService(database_path)
    recovered = await restarted_service.get(12)

    assert recovered is not None
    assert recovered.draft_id == created.draft_id
    assert recovered.draft_data["account_name"] == "Firm A"


@pytest.mark.asyncio
async def test_cancel_removes_draft(tmp_path) -> None:
    service = DraftService(tmp_path / "shop.db")
    await service.start_or_resume(12)

    assert await service.cancel(12) is True
    assert await service.cancel(12) is False
    assert await service.get(12) is None


@pytest.mark.asyncio
async def test_cleanup_removes_expired_but_skips_committing(tmp_path) -> None:
    database_path = tmp_path / "shop.db"
    service = DraftService(database_path)
    await service.start_or_resume(12)
    await service.start_or_resume(34)
    await service.merge(34, {}, state="COMMITTING")
    expired_at = (datetime.now(service._timezone) - timedelta(minutes=1)).isoformat()

    async with connect(database_path) as connection:
        await connection.execute(
            "UPDATE bill_drafts SET expires_at = ? WHERE telegram_user_id IN (?, ?)",
            (expired_at, 12, 34),
        )
        await connection.commit()

    assert await service.cleanup_expired() == 1
    assert await service.get(12) is None
    assert (await service.get(34)).state == "COMMITTING"

