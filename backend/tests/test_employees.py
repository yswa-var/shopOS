from uuid import uuid4

from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.models import AuditEvent, UserPermission


def test_owner_manages_employees_and_changes_take_effect_immediately(client, db_engine):
    owner_id, worker_id = seed_owner_and_employee(db_engine)
    owner = auth_headers(client)
    worker = auth_headers(client, "worker", "a-long-worker-password")
    with Session(db_engine) as db:
        db.add(UserPermission(user_id=worker_id, permission="employees:manage"))
        db.commit()

    creation = {"username": " Clerk.ONE ", "display_name": "  Counter   Clerk ", "password": "first-long-password"}
    assert client.get("/employees").status_code == 401
    assert client.get("/employees", headers=worker).status_code == 403
    assert client.get("/employees/permissions", headers=worker).status_code == 403
    assert client.post("/employees", json=creation, headers=worker).status_code == 403
    catalog = client.get("/employees/permissions", headers=owner)
    assert catalog.status_code == 200
    assert {entry["key"] for entry in catalog.json()} == {"catalog:read", "catalog:write", "bills:create", "bills:read", "attachments:write", "attachments:read"}

    created = client.post("/employees", json=creation, headers=owner)
    assert created.status_code == 201
    employee_id = created.json()["id"]
    assert created.json()["username"] == "clerk.one"
    assert created.json()["display_name"] == "Counter Clerk"
    assert created.json()["is_active"]
    assert len(created.json()["permissions"]) == 6
    assert "password" not in created.json()
    assert "password_hash" not in created.json()
    assert client.post("/employees", json=creation, headers=owner).status_code == 409
    assert client.post("/employees", json={**creation, "username": "other", "permissions": ["owner"]}, headers=owner).status_code == 422
    assert client.post("/employees", json={**creation, "username": "other", "password": "short"}, headers=owner).status_code == 422
    assert len(client.get("/employees", headers=owner).json()) == 2
    assert client.put(f"/employees/{owner_id}/status", json={"is_active": False}, headers=owner).status_code == 404

    clerk = auth_headers(client, "clerk.one", "first-long-password")
    assert client.get("/bills", headers=clerk).status_code == 200
    assert client.put(f"/employees/{employee_id}/permissions", json={"permissions": []}, headers=worker).status_code == 403
    assert client.put(f"/employees/{employee_id}/status", json={"is_active": False}, headers=worker).status_code == 403
    assert client.put(f"/employees/{employee_id}/password", json={"password": "new-long-password"}, headers=worker).status_code == 403
    assert client.put(f"/employees/{employee_id}/profile", json={"display_name": "Other"}, headers=worker).status_code == 403
    assert client.put(f"/employees/{employee_id}/permissions", json={"permissions": ["bills:read", "bills:read"]}, headers=owner).status_code == 422
    changed = client.put(f"/employees/{employee_id}/permissions", json={"permissions": ["catalog:read"]}, headers=owner)
    assert changed.status_code == 200
    assert changed.json()["permissions"] == ["catalog:read"]
    assert client.get("/bills", headers=clerk).status_code == 403
    assert client.get("/catalog/vendors", headers=clerk).status_code == 200

    profile = client.put(f"/employees/{employee_id}/profile", json={"display_name": "New Clerk"}, headers=owner)
    assert profile.json()["display_name"] == "New Clerk"
    assert client.put(f"/employees/{employee_id}/profile", json={"display_name": "  "}, headers=owner).status_code == 422
    assert client.put(f"/employees/{employee_id}/password", json={"password": "second-long-password"}, headers=owner).status_code == 204
    assert client.get("/auth/me", headers=clerk).status_code == 401
    assert client.post("/auth/login", json={"username": "clerk.one", "password": "first-long-password"}).status_code == 401
    clerk = auth_headers(client, "clerk.one", "second-long-password")

    inactive = client.put(f"/employees/{employee_id}/status", json={"is_active": False}, headers=owner)
    assert inactive.status_code == 200
    assert not inactive.json()["is_active"]
    assert client.get("/auth/me", headers=clerk).status_code == 401
    assert client.post("/auth/login", json={"username": "clerk.one", "password": "second-long-password"}).status_code == 401
    assert client.put(f"/employees/{employee_id}/status", json={"is_active": True}, headers=owner).json()["is_active"]
    assert client.get("/auth/me", headers=clerk).status_code == 401
    assert auth_headers(client, "clerk.one", "second-long-password")
    assert client.put(f"/employees/{uuid4()}/permissions", json={"permissions": []}, headers=owner).status_code == 404

    with Session(db_engine) as db:
        actions = [event.action for event in db.query(AuditEvent).filter_by(target_id=employee_id).all()]
    assert actions.count("employee.create") == 1
    assert actions.count("employee.permissions.update") == 1
    assert actions.count("employee.profile.update") == 1
    assert actions.count("employee.password.reset") == 1
    assert actions.count("employee.deactivate") == 1
    assert actions.count("employee.activate") == 1
