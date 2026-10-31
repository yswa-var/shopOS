from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from repositories import BillRepository, RecordNotFoundError, RequestConflictError
from schemas import BillCreate


class TransactionDatabase:
    def __init__(self, connection: AsyncMock) -> None:
        self.connection = connection

    async def execute(self, operation):
        return await operation(self.connection)


def bill_payload(**changes) -> BillCreate:
    values = {
        "vendor_id": 3,
        "due_date": "2026-11-15",
        "document_url": "https://files.example.com/invoice.jpg",
        "items": [{"item_id": 10, "quantity": "2.000"}],
        "charges": "10.00",
        "tax": "0.00",
        "tags": "spices, Spices, wholesale",
        "paid_amount": "0.00",
    }
    values.update(changes)
    return BillCreate.model_validate(values)


@pytest.mark.asyncio
async def test_bill_create_uses_catalog_price_and_inserts_atomically() -> None:
    connection = AsyncMock()
    connection.fetchval.side_effect = [True, 21, 22]
    connection.fetch.return_value = [{"id": 10, "purchase_price": Decimal("5.00")}]
    connection.fetchrow.side_effect = [
        {
            "id": 1001,
            "vendor_id": 3,
            "due_date": bill_payload().due_date,
            "document_url": "https://files.example.com/invoice.jpg",
            "is_paid": False,
            "paid_amount": Decimal("0.00"),
        },
        {
            "subtotal": Decimal("10.00"),
            "total_amount": Decimal("20.00"),
            "balance_due": Decimal("20.00"),
        },
    ]
    repository = BillRepository(TransactionDatabase(connection))

    result = await repository.create(bill_payload())

    assert result["id"] == 1001
    inserted_lines = connection.executemany.await_args.args[1]
    assert inserted_lines == [(1001, 1, 10, Decimal("2.000"), Decimal("5.00"))]
    assert connection.fetchval.await_count == 3
    assert connection.execute.await_count == 2


@pytest.mark.asyncio
async def test_bill_create_rejects_missing_vendor() -> None:
    connection = AsyncMock()
    connection.fetchval.return_value = False
    repository = BillRepository(TransactionDatabase(connection))

    with pytest.raises(RecordNotFoundError, match="Vendor"):
        await repository.create(bill_payload())

    connection.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_bill_create_rejects_payment_above_total() -> None:
    connection = AsyncMock()
    connection.fetchval.return_value = True
    connection.fetch.return_value = [{"id": 10, "purchase_price": Decimal("5.00")}]
    repository = BillRepository(TransactionDatabase(connection))

    with pytest.raises(RequestConflictError, match="exceed"):
        await repository.create(bill_payload(paid_amount="20.01"))

    connection.fetchrow.assert_not_awaited()


def test_tags_are_trimmed_and_deduplicated_case_insensitively() -> None:
    assert BillRepository._parse_tags(" spices, Spices, wholesale, ") == [
        "spices",
        "wholesale",
    ]
