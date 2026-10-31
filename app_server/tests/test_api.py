from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from db import Database
from main import app
from repositories import BillRepository, CatalogRepository, RecordNotFoundError
from routes import get_bills, get_catalog, get_database


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_transport() -> httpx.ASGITransport:
    return httpx.ASGITransport(app=app)


@pytest.mark.asyncio
async def test_root(client_transport: httpx.ASGITransport) -> None:
    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "ShopOS Bill Creator API"


@pytest.mark.asyncio
async def test_health_checks_database(client_transport: httpx.ASGITransport) -> None:
    database = AsyncMock(spec=Database)
    database.fetch_one.return_value = {"ok": 1}
    app.dependency_overrides[get_database] = lambda: database

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    database.fetch_one.assert_awaited_once_with("SELECT 1 AS ok")


@pytest.mark.asyncio
async def test_health_returns_503_when_database_fails(
    client_transport: httpx.ASGITransport,
) -> None:
    database = AsyncMock(spec=Database)
    database.fetch_one.side_effect = RuntimeError("offline")
    app.dependency_overrides[get_database] = lambda: database

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.asyncio
async def test_vendor_catalog_and_create(
    client_transport: httpx.ASGITransport,
) -> None:
    catalog = AsyncMock(spec=CatalogRepository)
    catalog.list_vendors.return_value = [
        {"id": 1, "name": "ABC Traders", "address": None, "phone_number": None}
    ]
    catalog.create_vendor.return_value = {
        "id": 2,
        "name": "New Vendor",
        "address": "Aligarh",
        "phone_number": None,
    }
    app.dependency_overrides[get_catalog] = lambda: catalog

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        listed = await client.get("/vendors")
        created = await client.post(
            "/vendors", json={"name": "  New Vendor  ", "address": "Aligarh"}
        )

    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "ABC Traders"
    assert created.status_code == 201
    assert created.json()["id"] == 2
    assert catalog.create_vendor.await_args.args[0].name == "New Vendor"


@pytest.mark.asyncio
async def test_item_catalog_uses_decimal_strings(
    client_transport: httpx.ASGITransport,
) -> None:
    catalog = AsyncMock(spec=CatalogRepository)
    catalog.list_items.return_value = [
        {
            "id": 10,
            "name": "Turmeric",
            "unit": "kg",
            "purchase_price": Decimal("160.00"),
            "sell_price": Decimal("220.00"),
        }
    ]
    catalog.create_item.return_value = {
        "id": 11,
        "name": "Cumin",
        "unit": "kg",
        "purchase_price": Decimal("450.00"),
        "sell_price": None,
    }
    app.dependency_overrides[get_catalog] = lambda: catalog

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        listed = await client.get("/items")
        created = await client.post(
            "/items",
            json={
                "name": "Cumin",
                "unit": "kg",
                "purchase_price": "450.00",
                "sell_price": None,
            },
        )

    assert listed.json()[0]["purchase_price"] == "160.00"
    assert created.status_code == 201
    assert created.json()["sell_price"] is None


@pytest.mark.asyncio
async def test_create_and_get_bill(client_transport: httpx.ASGITransport) -> None:
    bills = AsyncMock(spec=BillRepository)
    summary = {
        "id": 1001,
        "vendor_id": 3,
        "due_date": "2026-11-15",
        "document_url": "https://files.example.com/invoice.jpg",
        "is_paid": False,
        "paid_amount": Decimal("0.00"),
        "subtotal": Decimal("797.50"),
        "total_amount": Decimal("837.50"),
        "balance_due": Decimal("837.50"),
    }
    bills.create.return_value = summary
    bills.get.return_value = summary | {
        "charges": Decimal("40.00"),
        "tax": Decimal("0.00"),
        "notes": None,
        "items": [
            {
                "line_number": 1,
                "item_id": 10,
                "item_name": "Turmeric",
                "unit": "kg",
                "quantity": Decimal("5.000"),
                "purchase_unit_price": Decimal("159.50"),
                "line_total": Decimal("797.50"),
            }
        ],
        "tags": ["spices"],
    }
    app.dependency_overrides[get_bills] = lambda: bills
    request = {
        "vendor_id": 3,
        "due_date": "2026-11-15",
        "document_url": "https://files.example.com/invoice.jpg",
        "items": [
            {"item_id": 10, "quantity": "5.000", "purchase_unit_price": "159.50"}
        ],
        "charges": "40.00",
        "tags": "spices",
    }

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        created = await client.post("/bills", json=request)
        fetched = await client.get("/bills/1001")

    assert created.status_code == 201
    assert created.json()["total_amount"] == "837.50"
    assert fetched.status_code == 200
    assert fetched.json()["items"][0]["purchase_unit_price"] == "159.50"
    assert fetched.json()["tags"] == ["spices"]


@pytest.mark.asyncio
async def test_bill_not_found_returns_404(
    client_transport: httpx.ASGITransport,
) -> None:
    bills = AsyncMock(spec=BillRepository)
    bills.get.side_effect = RecordNotFoundError("Bill not found")
    app.dependency_overrides[get_bills] = lambda: bills

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        response = await client.get("/bills/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Bill not found"}


@pytest.mark.asyncio
async def test_empty_bill_is_rejected_before_repository(
    client_transport: httpx.ASGITransport,
) -> None:
    bills = AsyncMock(spec=BillRepository)
    app.dependency_overrides[get_bills] = lambda: bills

    async with httpx.AsyncClient(
        transport=client_transport, base_url="http://test"
    ) as client:
        response = await client.post(
            "/bills",
            json={
                "vendor_id": 1,
                "due_date": "2026-11-15",
                "document_url": "https://files.example.com/invoice.jpg",
                "items": [],
            },
        )

    assert response.status_code == 422
    bills.create.assert_not_awaited()
