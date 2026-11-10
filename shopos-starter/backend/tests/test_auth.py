from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from conftest import seed_owner_and_employee
from shopos.auth import require_permission
from shopos.bootstrap import create_first_owner
from shopos.models import AuditEvent, AuthSession, User, UserPermission
from shopos.security import hash_token


def login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_login_me_logout_and_audit(client, db_engine):
    owner_id, _ = seed_owner_and_employee(db_engine)
    assert login(client, "owner", "wrong-password").status_code == 401
    response = login(client, " OWNER ", "a-long-owner-password")
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=headers).json()["role"] == "owner"
    assert client.get("/audit/events", headers=headers).status_code == 200
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401
    with Session(db_engine) as db:
        assert db.query(AuditEvent).filter_by(actor_id=owner_id, action="auth.logout").count() == 1
        assert db.query(AuditEvent).filter_by(actor_id=owner_id, action="owner.bootstrap").count() == 1
        assert db.query(User).filter_by(username="owner").one().password_hash != "a-long-owner-password"
        assert db.query(User).filter_by(username="owner").one().id == owner_id


def test_employee_cannot_read_owner_audit_or_bypass_auth(client, db_engine):
    seed_owner_and_employee(db_engine)
    assert client.get("/auth/me").status_code == 401
    assert client.get("/audit/events").status_code == 401
    response = login(client, "worker", "a-long-worker-password")
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/auth/me", headers=headers).json()["permissions"] == ["bills:create"]
    assert client.get("/audit/events", headers=headers).status_code == 403
    with Session(db_engine) as db:
        employee = db.query(User).filter_by(username="worker").one()
        assert require_permission("bills:create")(employee) is employee
        with pytest.raises(HTTPException) as denied:
            require_permission("catalog:write")(employee)
        assert denied.value.status_code == 403
        db.add(UserPermission(user_id=employee.id, permission="audit:read"))
        db.commit()
    # Audit remains owner-only even if an employee receives an audit permission.
    assert client.get("/audit/events", headers=headers).status_code == 403
    with Session(db_engine) as db:
        employee = db.query(User).filter_by(username="worker").one()
        employee.is_active = False
        db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_bootstrap_only_once_and_tokens_are_hashed(client, db_engine):
    seed_owner_and_employee(db_engine)
    with Session(db_engine) as db:
        with pytest.raises(ValueError, match="first user"):
            create_first_owner(db, username="another", display_name="Another", password="another-long-password")
        db.rollback()
    token = login(client, "owner", "a-long-owner-password").json()["access_token"]
    with Session(db_engine) as db:
        saved = db.query(AuthSession).one()
        assert saved.token_hash == hash_token(token)
        assert token not in saved.token_hash
        saved.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
