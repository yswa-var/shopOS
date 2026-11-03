import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from shopos.auth import get_db
from shopos.bootstrap import create_first_owner
from shopos.config import database_url
from shopos.db import Base
from shopos.main import app
from shopos.models import User, UserPermission
from shopos.security import hash_password


@pytest.fixture
def db_engine():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL required for PostgreSQL integration tests")
    schema = "test_" + uuid4().hex
    admin_engine = create_engine(database_url())
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(database_url(), connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def client(db_engine):
    def test_db():
        with Session(db_engine) as db:
            yield db
    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def seed_owner_and_employee(db_engine):
    with Session(db_engine) as db:
        owner = create_first_owner(db, username="owner", display_name="Owner", password="a-long-owner-password")
        employee = User(username="worker", display_name="Worker", password_hash=hash_password("a-long-worker-password"), role="employee")
        db.add(employee)
        db.flush()
        db.add(UserPermission(user_id=employee.id, permission="bills:create"))
        db.commit()
        return owner.id, employee.id


def auth_headers(client, username="owner", password="a-long-owner-password"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
