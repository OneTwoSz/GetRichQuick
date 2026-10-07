"""
Login-free links: expiry, revocation, submission caps and per-IP limits for
buyer share links, job-work links and supplier data requests.
"""
from datetime import timedelta

from app.database import get_db
from app.main import app
from app.models import Order, ProductionBatch, SupplierDataRequest
from app.utils.timeutil import utcnow


def _db():
    return next(app.dependency_overrides[get_db]())


def _order(client):
    pid = client.post("/api/products", json={"sku": "TEE", "name": "Tee", "garment_weight_g": 200}).json()["id"]
    return client.post("/api/orders", json={"order_code": "PO-1", "product_id": pid, "units": 100}).json()


def _outsourced_batch(client):
    r = client.post("/api/batches", json={
        "batch_code": "LOT-JW", "process_type": "dyeing", "started_at": "2026-07-01T08:00:00Z",
        "total_fabric_kg": 100, "outsourced": True,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _supplier_request(client):
    s = client.post("/api/suppliers", json={"name": "Spinner", "stage": "yarn_production"}).json()
    return s, client.post(f"/api/suppliers/{s['id']}/data-requests", json={}).json()


JOBWORK_INPUT = {"inputs": [{"input_type": "water_l", "quantity": 1000, "data_quality": "measured"}]}
SUPPLIER_DATA = {"output_kg": 1000, "electricity_kwh": 3000}


# --- buyer share links -----------------------------------------------------------

def test_share_link_expires_and_can_be_revoked_and_rotated(client):
    order = _order(client)
    shared = client.post(f"/api/orders/{order['id']}/share-link").json()
    token = shared["share_token"]
    assert shared["share_expires_at"]                       # defaults to 90 days
    assert client.get(f"/api/share/{token}").status_code == 200

    # Asking again returns the same live link; rotate issues a new one.
    assert client.post(f"/api/orders/{order['id']}/share-link").json()["share_token"] == token
    rotated = client.post(f"/api/orders/{order['id']}/share-link?rotate=true").json()["share_token"]
    assert rotated != token
    assert client.get(f"/api/share/{token}").status_code == 404

    db = _db()
    row = db.query(Order).get(order["id"])
    row.share_expires_at = utcnow() - timedelta(minutes=1)
    db.commit()
    expired = client.get(f"/api/share/{rotated}")
    assert expired.status_code == 410 and "expired" in expired.json()["detail"]

    fresh = client.post(f"/api/orders/{order['id']}/share-link").json()["share_token"]
    assert fresh != rotated                                 # expired links are replaced
    revoked = client.delete(f"/api/orders/{order['id']}/share-link").json()
    assert revoked["share_token"] is None
    assert client.get(f"/api/share/{fresh}").status_code == 404


def test_legacy_links_without_expiry_keep_working(client):
    order = _order(client)
    db = _db()
    row = db.query(Order).get(order["id"])
    row.share_token, row.share_expires_at = "legacy-token-abc", None
    db.commit()
    assert client.get("/api/share/legacy-token-abc").status_code == 200


# --- job-work links -----------------------------------------------------------------

def test_jobwork_link_caps_submissions(client):
    batch = _outsourced_batch(client)
    link = client.post(f"/api/batches/{batch['id']}/jobwork-link").json()
    token = link["job_work_token"]
    assert link["job_work_expires_at"] and link["job_work_submissions"] == 0

    info = client.get(f"/api/jobwork/{token}").json()
    assert info["submissions_left"] == 5
    for _ in range(5):
        assert client.post(f"/api/jobwork/{token}", json=JOBWORK_INPUT).status_code == 201
    over = client.post(f"/api/jobwork/{token}", json=JOBWORK_INPUT)
    assert over.status_code == 429 and "submission limit" in over.json()["detail"]
    assert client.get(f"/api/jobwork/{token}").json()["submissions_left"] == 0

    # A rotated link starts a fresh allowance; the old one is dead.
    new = client.post(f"/api/batches/{batch['id']}/jobwork-link?rotate=true").json()["job_work_token"]
    assert client.get(f"/api/jobwork/{token}").status_code == 404
    assert client.get(f"/api/jobwork/{new}").json()["submissions_left"] == 5


def test_jobwork_link_expiry_and_revocation(client):
    batch = _outsourced_batch(client)
    token = client.post(f"/api/batches/{batch['id']}/jobwork-link").json()["job_work_token"]
    db = _db()
    row = db.query(ProductionBatch).get(batch["id"])
    row.job_work_expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert client.get(f"/api/jobwork/{token}").status_code == 410
    assert client.post(f"/api/jobwork/{token}", json=JOBWORK_INPUT).status_code == 410

    token = client.post(f"/api/batches/{batch['id']}/jobwork-link").json()["job_work_token"]
    assert client.delete(f"/api/batches/{batch['id']}/jobwork-link").json()["job_work_token"] is None
    assert client.get(f"/api/jobwork/{token}").status_code == 404


# --- supplier data requests ------------------------------------------------------------

def test_supplier_link_limits_expiry_and_revocation(client):
    supplier, req = _supplier_request(client)
    token = req["token"]
    assert req["expires_at"] and req["max_submissions"] == 3 and req["submissions"] == 0

    for _ in range(3):
        assert client.post(f"/api/supplier-data/{token}", json=SUPPLIER_DATA).status_code == 201
    assert client.post(f"/api/supplier-data/{token}", json=SUPPLIER_DATA).status_code == 429
    listed = client.get(f"/api/suppliers/{supplier['id']}/data-requests").json()
    assert listed[0]["submissions"] == 3

    _, req2 = _supplier_request(client)
    revoked = client.delete(f"/api/suppliers/{req2['supplier_id']}/data-requests/{req2['id']}").json()
    assert revoked["revoked_at"]
    r = client.get(f"/api/supplier-data/{req2['token']}")
    assert r.status_code == 410 and "no longer valid" in r.json()["detail"]

    _, req3 = _supplier_request(client)
    db = _db()
    row = db.query(SupplierDataRequest).get(req3["id"])
    row.expires_at = utcnow() - timedelta(hours=1)
    db.commit()
    assert client.post(f"/api/supplier-data/{req3['token']}", json=SUPPLIER_DATA).status_code == 410


def test_public_lookups_are_rate_limited_per_ip(client):
    for _ in range(120):
        client.get("/api/share/no-such-token")
    assert client.get("/api/share/no-such-token").status_code == 429  # can't brute-force tokens


def test_public_submissions_are_rate_limited_per_ip(client):
    # Ten submissions per hour per IP across all supplier links.
    statuses = []
    for _ in range(4):
        _, req = _supplier_request(client)
        for _ in range(3):
            statuses.append(client.post(f"/api/supplier-data/{req['token']}", json=SUPPLIER_DATA).status_code)
    assert statuses.count(201) == 10
    assert statuses[-1] == 429
