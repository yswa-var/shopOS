import httpx
import pytest

from auth import password_hash
from main import app
from db import get_database


class FakeDatabase:
    async def fetch_one(self, query, parameters=()):
        if parameters == ("alice",):
            return {"password_hash": password_hash.hash("correct-password"), "is_active": True}
        if parameters == ("disabled",):
            return {"password_hash": password_hash.hash("correct-password"), "is_active": False}
        return None


@pytest.mark.asyncio
async def test_catalog_requires_login():
    app.dependency_overrides[get_database] = lambda: FakeDatabase()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/vendors")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_user_and_bad_password():
    app.dependency_overrides[get_database] = lambda: FakeDatabase()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            valid = await client.get("/auth/me", auth=("alice", "correct-password"))
            invalid = await client.get("/auth/me", auth=("alice", "wrong"))
            disabled = await client.get("/auth/me", auth=("disabled", "correct-password"))
    finally:
        app.dependency_overrides.clear()
    assert valid.status_code == 200
    assert valid.json() == {"username": "alice"}
    assert invalid.status_code == 401
    assert disabled.status_code == 401
