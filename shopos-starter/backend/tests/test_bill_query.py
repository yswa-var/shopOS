from uuid import uuid4

from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.main import app
from shopos.models import CatalogTerm, Item, ProofAttachment, UserPermission, Vendor
from shopos.storage import get_storage


def catalog_and_proof(db_engine, creator, suffix):
    with Session(db_engine) as db:
        vendor = Vendor(name=f"Vendor {suffix}", normalized_name=f"vendor {suffix.lower()}", created_by=creator)
        item = Item(name=f"Item {suffix}", normalized_name=f"item {suffix.lower()}", created_by=creator)
        proof = ProofAttachment(client_upload_id=uuid4(), uploaded_by=creator, content_type="image/jpeg", size_bytes=3, upload_key=f"pending/{uuid4()}", object_key=f"proofs/{uuid4()}", status="ready")
        db.add_all([vendor, item, proof])
        db.flush()
        db.add_all([
            CatalogTerm(kind="vendor", display_term=vendor.name, normalized_term=vendor.normalized_name, vendor_id=vendor.id),
            CatalogTerm(kind="vendor", display_term=f"Alias {suffix}", normalized_term=f"alias {suffix.lower()}", vendor_id=vendor.id),
            CatalogTerm(kind="item", display_term=item.name, normalized_term=item.normalized_name, item_id=item.id),
            CatalogTerm(kind="item", display_term=f"Stock {suffix}", normalized_term=f"stock {suffix.lower()}", item_id=item.id),
        ])
        db.commit()
        return vendor.id, item.id, proof.id


def bill_payload(vendor, item, proof, day, amount):
    return {"vendor_id": str(vendor), "bill_date": day, "proof_attachment_id": str(proof), "idempotency_key": str(uuid4()), "items": [{"item_id": str(item), "quantity": "1", "price_basis": "amount", "line_amount": amount}]}


def test_search_filters_detail_and_linked_proof_policy(client, db_engine):
    owner_id, worker_id = seed_owner_and_employee(db_engine)
    owner = auth_headers(client)
    worker = auth_headers(client, "worker", "a-long-worker-password")
    a_vendor, a_item, a_proof = catalog_and_proof(db_engine, owner_id, "Alpha")
    b_vendor, b_item, b_proof = catalog_and_proof(db_engine, worker_id, "Beta")
    first = client.post("/bills", json=bill_payload(a_vendor, a_item, a_proof, "2026-11-01", "25.00"), headers=owner)
    second = client.post("/bills", json=bill_payload(b_vendor, b_item, b_proof, "2026-11-03", "75.00"), headers=worker)
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()["id"], second.json()["id"]

    assert client.get("/bills").status_code == 401
    assert client.get("/bills", headers=worker).status_code == 403
    assert client.get(f"/bills/{second_id}", headers=worker).status_code == 403
    with Session(db_engine) as db:
        db.add(UserPermission(user_id=worker_id, permission="attachments:read"))
        db.commit()
    assert client.get(f"/attachments/proofs/{b_proof}", headers=worker).status_code == 403
    with Session(db_engine) as db:
        db.add(UserPermission(user_id=worker_id, permission="bills:read"))
        db.query(UserPermission).filter_by(user_id=worker_id, permission="attachments:read").delete()
        db.commit()

    all_rows = client.get("/bills", headers=worker).json()
    assert [row["id"] for row in all_rows["rows"]] == [second_id, first_id]
    assert all_rows["rows"][0]["item_names"] == ["Item Beta"]
    assert not all_rows["has_more"]
    assert client.get("/bills?vendor=alias%20alpha", headers=worker).json()["rows"][0]["id"] == first_id
    assert client.get("/bills?item=stock%20beta", headers=worker).json()["rows"][0]["id"] == second_id
    assert client.get("/bills?employee=work", headers=worker).json()["rows"][0]["id"] == second_id
    assert client.get("/bills?employee=worker", headers=worker).json()["rows"][0]["id"] == second_id
    assert client.get("/bills?date_from=2026-11-02&date_to=2026-11-04", headers=worker).json()["rows"][0]["id"] == second_id
    assert client.get("/bills?amount_min=20&amount_max=30", headers=worker).json()["rows"][0]["id"] == first_id
    assert client.get("/bills?vendor=%25", headers=worker).json()["rows"] == []
    assert client.get("/bills?vendor=alpha&item=stock%20beta", headers=worker).json()["rows"] == []
    assert client.get("/bills?limit=1", headers=worker).json()["has_more"]
    assert client.get("/bills?limit=1&offset=1", headers=worker).json()["rows"][0]["id"] == first_id
    for query in ("date_from=2026-11-05&date_to=2026-11-01", "amount_min=-1", "amount_min=100&amount_max=1", "limit=101"):
        assert client.get(f"/bills?{query}", headers=worker).status_code == 422

    detail = client.get(f"/bills/{first_id}", headers=worker)
    assert detail.status_code == 200
    assert detail.json()["vendor_name"] == "Vendor Alpha"
    assert detail.json()["employee_name"] == "Owner"
    assert detail.json()["items"][0]["item_name"] == "Item Alpha"
    assert client.get(f"/bills/{uuid4()}", headers=worker).status_code == 404

    class SignedStorage:
        def download_url(self, key):
            return f"https://storage.test/{key}?signed=short"

    app.dependency_overrides[get_storage] = lambda: SignedStorage()
    try:
        url = client.get(f"/attachments/proofs/{a_proof}/download", headers=worker)
        assert url.status_code == 200
        assert "signed=short" in url.json()["download_url"]
        assert client.get(f"/attachments/proofs/{a_proof}", headers=worker).status_code == 200
    finally:
        app.dependency_overrides.pop(get_storage, None)
