from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy.orm import Session

from conftest import auth_headers, seed_owner_and_employee
from shopos.models import AuditEvent, Bill, BillLine, Item, ProofAttachment, Vendor


def setup_catalog_and_proof(db_engine, user_id, *, proof_status="ready"):
    with Session(db_engine) as db:
        suffix = str(user_id)[:8]
        vendor = Vendor(name=f"Synthetic Vendor {suffix}", normalized_name=f"synthetic vendor {suffix}", created_by=user_id)
        first = Item(name=f"First Item {suffix}", normalized_name=f"first item {suffix}", created_by=user_id)
        second = Item(name=f"Second Item {suffix}", normalized_name=f"second item {suffix}", created_by=user_id)
        proof = ProofAttachment(client_upload_id=uuid4(), uploaded_by=user_id, content_type="image/jpeg", size_bytes=16, upload_key=f"pending/{uuid4()}", object_key=f"proofs/{uuid4()}", status=proof_status)
        db.add_all([vendor, first, second, proof])
        db.commit()
        return vendor.id, first.id, second.id, proof.id


def payload(vendor_id, item_ids, proof_id, key=None):
    return {
        "vendor_id": str(vendor_id),
        "bill_date": "2026-11-04",
        "proof_attachment_id": str(proof_id),
        "idempotency_key": str(key or uuid4()),
        "items": [
            {"item_id": str(item_ids[0]), "quantity": "2", "price_basis": "rate", "unit_rate": "12.3456"},
            {"item_id": str(item_ids[1]), "quantity": "3", "price_basis": "amount", "line_amount": "100.00"},
        ],
        "tax_amount": "5.50",
        "charges_amount": "1.25",
    }


def test_multi_item_save_is_idempotent_and_audited(client, db_engine):
    owner_id, _ = seed_owner_and_employee(db_engine)
    vendor_id, first_id, second_id, proof_id = setup_catalog_and_proof(db_engine, owner_id)
    headers = auth_headers(client)
    request = payload(vendor_id, [first_id, second_id], proof_id)

    first = client.post("/bills", json=request, headers=headers)
    assert first.status_code == 201
    assert first.json()["subtotal"] == "124.69"
    assert first.json()["total_amount"] == "131.44"
    assert [line["price_basis"] for line in first.json()["items"]] == ["rate", "amount"]
    assert [line["unit_rate"] for line in first.json()["items"]] == ["12.3456", "33.3333"]
    assert client.post("/bills", json=request, headers=headers).json() == first.json()

    with Session(db_engine) as db:
        assert db.query(Bill).count() == 1
        assert db.query(BillLine).count() == 2
        assert db.query(AuditEvent).filter_by(action="bill.create").count() == 1
        assert db.get(Vendor, vendor_id).use_count == 1
        assert db.get(Item, first_id).use_count == 1
        assert db.get(Item, second_id).use_count == 1

    changed = dict(request, charges_amount="2.00")
    assert client.post("/bills", json=changed, headers=headers).status_code == 409
    reuse_proof = dict(request, idempotency_key=str(uuid4()))
    assert client.post("/bills", json=reuse_proof, headers=headers).status_code == 409


def test_missing_or_foreign_proof_and_catalog_are_rejected(client, db_engine):
    owner_id, worker_id = seed_owner_and_employee(db_engine)
    vendor_id, first_id, second_id, pending_id = setup_catalog_and_proof(db_engine, owner_id, proof_status="pending")
    owner = auth_headers(client)
    worker = auth_headers(client, "worker", "a-long-worker-password")
    request = payload(vendor_id, [first_id, second_id], pending_id)
    assert client.post("/bills", json=request).status_code == 401
    assert client.post("/bills", json=request, headers=owner).status_code == 409
    assert client.post("/bills", json=request, headers=worker).status_code == 403

    with Session(db_engine) as db:
        db.get(ProofAttachment, pending_id).status = "ready"
        db.commit()
    assert client.post("/bills", json=request, headers=worker).status_code == 403
    no_photo = dict(request)
    no_photo.pop("proof_attachment_id")
    assert client.post("/bills", json=no_photo, headers=owner).status_code == 422
    missing_vendor = dict(request, vendor_id=str(uuid4()))
    assert client.post("/bills", json=missing_vendor, headers=owner).status_code == 422
    missing_item = dict(request, items=[dict(request["items"][0], item_id=str(uuid4()))])
    assert client.post("/bills", json=missing_item, headers=owner).status_code == 422

    worker_vendor, worker_first, worker_second, worker_proof = setup_catalog_and_proof(db_engine, worker_id)
    worker_request = payload(worker_vendor, [worker_first, worker_second], worker_proof)
    assert client.post("/bills", json=worker_request, headers=worker).status_code == 201


def test_concurrent_retry_creates_one_bill(client, db_engine):
    owner_id, _ = seed_owner_and_employee(db_engine)
    vendor_id, first_id, second_id, proof_id = setup_catalog_and_proof(db_engine, owner_id)
    headers = auth_headers(client)
    request = payload(vendor_id, [first_id, second_id], proof_id)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: client.post("/bills", json=request, headers=headers), range(2)))
    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    with Session(db_engine) as db:
        assert db.query(Bill).count() == 1
