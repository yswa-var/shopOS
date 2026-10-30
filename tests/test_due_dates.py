from datetime import datetime
from zoneinfo import ZoneInfo

from shopos.services.bill_entry_service import normalize_due_at


def test_relative_due_date_becomes_iso_date() -> None:
    timezone = ZoneInfo("Asia/Kolkata")
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone)

    assert normalize_due_at("in 17 days", timezone, now=now) == "2026-11-14"
    assert normalize_due_at("2026-11-15", timezone, now=now) == "2026-11-15"
