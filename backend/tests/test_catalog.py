from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.models import AuditEvent, Item, UserPermission, Vendor


def grant(db_engine, user_id, *permissions):
    with Session(db_engine) as db:
        for permission in permissions:
            db.add(UserPermission(user_id=user_id, permission=permission))
        db.commit()


def test_vendor_and_item_search_aliases_and_duplicates(client, db_engine):
    _, employee_id = seed_owner_and_employee(db_engine)
    grant(db_engine, employee_id, "catalog:read", "catalog:write")
    headers = auth_headers(client, "worker", "a-long-worker-password")

    vendor = client.post("/catalog/vendors", json={"name": "  Green   Farms ", "aliases": ["GF", "Farm Green"]}, headers=headers)
    assert vendor.status_code == 201
    assert vendor.json()["name"] == "Green Farms"
    assert vendor.json()["aliases"] == ["Farm Green", "GF"]
    vendor_id = vendor.json()["id"]
    assert client.get("/catalog/vendors", params={"q": "gf"}, headers=headers).json()[0]["id"] == vendor_id
    assert client.get("/catalog/vendors", params={"q": "GREEN"}, headers=headers).json()[0]["id"] == vendor_id

    item = client.post("/catalog/items", json={"name": "Green Farms", "aliases": ["Green item"]}, headers=headers)
    assert item.status_code == 201  # Catalog kinds have separate namespaces.
    assert client.get("/catalog/items", params={"q": "item"}, headers=headers).json()[0]["id"] == item.json()["id"]

    duplicate_name = client.post("/catalog/vendors", json={"name": "green farms"}, headers=headers)
    assert duplicate_name.status_code == 409
    assert duplicate_name.json()["detail"]["existing_id"] == vendor_id
    duplicate_alias = client.post("/catalog/vendors", json={"name": "GF"}, headers=headers)
    assert duplicate_alias.status_code == 409
    assert duplicate_alias.json()["detail"]["existing_id"] == vendor_id
    assert client.post("/catalog/vendors", json={"name": "New", "aliases": ["new"]}, headers=headers).status_code == 422


def test_alias_addition_conflicts_and_audit(client, db_engine):
    seed_owner_and_employee(db_engine)
    headers = auth_headers(client)
    first = client.post("/catalog/vendors", json={"name": "First"}, headers=headers).json()
    second = client.post("/catalog/vendors", json={"name": "Second"}, headers=headers).json()
    response = client.post(f"/catalog/vendors/{first['id']}/aliases", json={"alias": "One"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["aliases"] == ["One"]
    assert client.get("/catalog/vendors", params={"q": "one"}, headers=headers).json()[0]["id"] == first["id"]
    conflict = client.post(f"/catalog/vendors/{second['id']}/aliases", json={"alias": "ONE"}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["existing_id"] == first["id"]
    assert client.post("/catalog/items/00000000-0000-0000-0000-000000000001/aliases", json={"alias": "Missing"}, headers=headers).status_code == 404
    with Session(db_engine) as db:
        assert db.query(AuditEvent).filter_by(action="catalog.vendor.create").count() == 2
        assert db.query(AuditEvent).filter_by(action="catalog.vendor.alias.create").count() == 1
        assert db.query(Vendor).count() == 2


def test_read_write_permissions_and_search_order(client, db_engine):
    _, employee_id = seed_owner_and_employee(db_engine)
    employee = auth_headers(client, "worker", "a-long-worker-password")
    owner = auth_headers(client)
    assert client.get("/catalog/items").status_code == 401
    assert client.get("/catalog/items", headers=employee).status_code == 403
    grant(db_engine, employee_id, "catalog:read")
    assert client.get("/catalog/items", headers=employee).status_code == 200
    assert client.post("/catalog/items", json={"name": "Rice"}, headers=employee).status_code == 403

    first = client.post("/catalog/items", json={"name": "Rice", "aliases": ["White Rice"]}, headers=owner).json()
    second = client.post("/catalog/items", json={"name": "Ricer"}, headers=owner).json()
    assert client.get("/catalog/items", params={"q": "rice"}, headers=employee).json()[0]["id"] == first["id"]
    with Session(db_engine) as db:
        item = db.get(Item, second["id"])
        item.use_count = 4
        db.commit()
    assert client.get("/catalog/items", headers=employee).json()[0]["id"] == second["id"]
    assert client.get("/catalog/items", params={"q": "%"}, headers=employee).json() == []
