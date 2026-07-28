"""
End-to-end batch → allocation → footprint flow through the API, against an
in-memory SQLite database. Covers the spec §10 acceptance criteria that
need the ORM layer (inventory transfer, rework, default-factor quality mix,
monthly reconciliation, share link).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db, json_serializer
from app.main import app
from app.models import Factory, User, UserRole
from app.utils.auth import get_current_user

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    json_serializer=json_serializer,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()

    user = User(email="mill@example.com", password_hash="x", name="Mill", role=UserRole.FACTORY_MANAGER)
    session.add(user)
    session.flush()
    factory = Factory(user_id=user.id, name="Tiruppur Knits", location="Tiruppur")
    session.add(factory)
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(bind=engine)


def _make_product(client, sku, weight_g, waste_pct):
    r = client.post("/api/products", json={
        "sku": sku, "name": sku, "garment_weight_g": weight_g,
        "cutting_waste_percent": waste_pct,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _make_order(client, code, product_id, units):
    r = client.post("/api/orders", json={
        "order_code": code, "product_id": product_id, "units": units,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _make_batch(client, code, fabric_kg, inputs=(), **extra):
    r = client.post("/api/batches", json={
        "batch_code": code, "process_type": "dyeing", "colour": "white",
        "started_at": "2026-07-01T08:00:00Z", "total_fabric_kg": fabric_kg,
        "inputs": list(inputs), **extra,
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_order_fabric_demand_from_style_waste(client):
    """Style with 20% cutting waste, 0.2 kg net weight, 1,000 units →
    fabric demand 250 kg (spec §10)."""
    product_id = _make_product(client, "TEE-01", 200, 20)
    order = _make_order(client, "PO-1", product_id, 1000)
    assert order["fabric_demand_kg"] == pytest.approx(250)


def test_full_batch_allocation_footprint_and_inventory(client):
    """1,000 kg batch, A 600 / B 350 / 50 kg leftover, 10,000 L water:
    A gets 6,000 L, inventory gets 5% of the footprint, shares sum to 1."""
    product_id = _make_product(client, "TEE-02", 200, 20)
    order_a = _make_order(client, "PO-A", product_id, 1000)
    order_b = _make_order(client, "PO-B", product_id, 1000)

    batch = _make_batch(client, "LOT-1", 1000, inputs=[
        {"input_type": "water_l", "quantity": 10000, "data_quality": "measured"},
        {"input_type": "electricity_kwh", "quantity": 1000, "data_quality": "measured"},
    ])

    r = client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order_a["id"], "fabric_kg": 600},
        {"order_id": order_b["id"], "fabric_kg": 350},
    ]})
    assert r.status_code == 200, r.text
    allocations = r.json()["allocations"]
    shares = {a["order_id"]: a["allocated_share"] for a in allocations}
    assert shares[order_a["id"]] == pytest.approx(0.6)
    assert shares[order_b["id"]] == pytest.approx(0.35)

    fp = client.get(f"/api/orders/{order_a['id']}/footprint").json()
    assert fp["water_l"] == pytest.approx(6000)
    assert fp["quality_mix"]["measured"] == pytest.approx(100)

    # Complete → leftover 50 kg flows to inventory with 5% of the footprint.
    r = client.post(f"/api/batches/{batch['id']}/complete")
    assert r.status_code == 200, r.text
    inventory = client.get("/api/inventory").json()
    assert len(inventory) == 1
    item = inventory[0]
    assert item["fabric_kg"] == pytest.approx(50)
    assert item["embodied_water_l"] == pytest.approx(500)
    # 5% of total CO2: water 10,000×0.0003 + power 1,000×0.85 = 853 kg → 42.65
    assert item["embodied_co2_kg"] == pytest.approx(853 * 0.05)

    # Order totals unchanged by the leftover.
    fp_after = client.get(f"/api/orders/{order_a['id']}/footprint").json()
    assert fp_after["water_l"] == pytest.approx(6000)

    # Consuming the leftover transfers the embodied footprint to that order.
    order_c = _make_order(client, "PO-C", product_id, 100)
    r = client.post(f"/api/inventory/{item['id']}/consume", json={"order_id": order_c["id"]})
    assert r.status_code == 200
    fp_c = client.get(f"/api/orders/{order_c['id']}/footprint").json()
    assert fp_c["embodied_water_l"] == pytest.approx(500)
    assert fp_c["embodied_co2_kg"] == pytest.approx(853 * 0.05)


def test_rework_batch_adds_pro_rata(client):
    """Rework batch adds its inputs to the original batch's orders pro rata."""
    product_id = _make_product(client, "TEE-03", 200, 20)
    order_a = _make_order(client, "PO-A", product_id, 1000)
    order_b = _make_order(client, "PO-B", product_id, 1000)

    original = _make_batch(client, "LOT-2", 1000, inputs=[
        {"input_type": "water_l", "quantity": 10000},
    ])
    client.post(f"/api/batches/{original['id']}/allocations", json={"lines": [
        {"order_id": order_a["id"], "fabric_kg": 600},
        {"order_id": order_b["id"], "fabric_kg": 400},
    ]})

    _make_batch(client, "LOT-2-RW", 1000, inputs=[
        {"input_type": "water_l", "quantity": 5000},
    ], is_rework=True, rework_of_batch_id=original["id"])

    fp_a = client.get(f"/api/orders/{order_a['id']}/footprint").json()
    fp_b = client.get(f"/api/orders/{order_b['id']}/footprint").json()
    assert fp_a["water_l"] == pytest.approx(6000 + 3000)
    assert fp_b["water_l"] == pytest.approx(4000 + 2000)
    assert any(line["is_rework"] for line in fp_a["batch_lines"])


def test_outsourced_default_factor_batch_quality_mix(client):
    """An order touched by an outsourced dye batch with no data uses the
    built-in defaults → data-quality mix ≠ 100% measured."""
    product_id = _make_product(client, "TEE-04", 200, 20)
    order = _make_order(client, "PO-D", product_id, 1000)

    r = client.post("/api/job-workers", json={"name": "Dye House", "process_type": "dyeing"})
    worker_id = r.json()["id"]
    batch = _make_batch(client, "LOT-3", 500, outsourced=True, job_worker_id=worker_id)
    client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order["id"], "fabric_kg": 500},
    ]})

    fp = client.get(f"/api/orders/{order['id']}/footprint").json()
    assert fp["quality_mix"]["measured"] < 100
    assert fp["quality_mix"]["default_factor"] == pytest.approx(100)
    assert fp["co2_kg"] > 0
    assert "default_factors" in fp["batch_lines"][0]["data_quality_flags"]


def test_jobwork_token_submission_upgrades_to_measured(client):
    """Job worker submits actuals through the login-free link; the batch
    switches from defaults to the submitted MEASURED figures."""
    product_id = _make_product(client, "TEE-05", 200, 20)
    order = _make_order(client, "PO-E", product_id, 1000)
    batch = _make_batch(client, "LOT-4", 500, outsourced=True)
    client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order["id"], "fabric_kg": 500},
    ]})

    token = client.post(f"/api/batches/{batch['id']}/jobwork-link").json()["job_work_token"]
    assert token

    info = client.get(f"/api/jobwork/{token}").json()
    assert info["batch_code"] == "LOT-4"
    assert info["already_submitted"] is False

    r = client.post(f"/api/jobwork/{token}", json={
        "submitted_by": "Dye House Supervisor",
        "inputs": [{"input_type": "water_l", "quantity": 30000, "data_quality": "measured"}],
    })
    assert r.status_code == 201

    fp = client.get(f"/api/orders/{order['id']}/footprint").json()
    assert fp["water_l"] == pytest.approx(30000)
    assert fp["quality_mix"]["measured"] == pytest.approx(100)


def test_monthly_reconciliation_overhead(client):
    """Monthly kWh 12,000 with 9,000 attributed → 3,000 kWh overhead spread
    by mass across the month's batches (spec §10)."""
    product_id = _make_product(client, "TEE-06", 200, 20)
    order_a = _make_order(client, "PO-F", product_id, 1000)
    order_b = _make_order(client, "PO-G", product_id, 1000)

    batch_a = _make_batch(client, "LOT-5", 600, inputs=[
        {"input_type": "electricity_kwh", "quantity": 5400},
    ])
    batch_b = _make_batch(client, "LOT-6", 400, inputs=[
        {"input_type": "electricity_kwh", "quantity": 3600},
    ])
    client.post(f"/api/batches/{batch_a['id']}/allocations", json={"lines": [
        {"order_id": order_a["id"], "fabric_kg": 600},
    ]})
    client.post(f"/api/batches/{batch_b['id']}/allocations", json={"lines": [
        {"order_id": order_b["id"], "fabric_kg": 400},
    ]})

    r = client.post("/api/utilities", json={
        "year": 2026, "month": 7,
        "total_electricity_kwh": 12000, "total_water_liters": 0,
    })
    assert r.status_code == 201

    recon = client.get("/api/utilities/reconcile/2026/7").json()
    assert recon["attributed_kwh"] == pytest.approx(9000)
    assert recon["overhead_kwh"] == pytest.approx(3000)
    per_batch = {v["batch_code"]: v for v in recon["per_batch"].values()}
    assert per_batch["LOT-5"]["overhead_kwh"] == pytest.approx(1800)
    assert per_batch["LOT-6"]["overhead_kwh"] == pytest.approx(1200)

    # The order footprint includes its overhead slice as ESTIMATED data.
    fp = client.get(f"/api/orders/{order_a['id']}/footprint").json()
    assert fp["overhead_co2_kg"] == pytest.approx(1800 * 0.85, rel=1e-3)
    assert fp["quality_mix"]["estimated"] > 0


def test_report_includes_allocation_statement_and_quality_mix(client, tmp_path):
    """Report for an order touched by an outsourced dye batch using default
    factors shows data-quality mix ≠ 100% measured (spec §10), and the
    rendered report carries the Allocation Statement."""
    from app.config import settings
    settings.REPORTS_DIR = str(tmp_path)

    product_id = _make_product(client, "TEE-08", 200, 20)
    order = _make_order(client, "PO-R", product_id, 1000)
    batch = _make_batch(client, "LOT-8", 500, outsourced=True)
    client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order["id"], "fabric_kg": 500},
    ]})

    r = client.post("/api/reports/generate", json={
        "date_from": "2026-06-01T00:00:00Z",
        "date_to": "2026-07-31T00:00:00Z",
        "report_type": "monthly",
    })
    assert r.status_code == 201, r.text

    rendered = [p for p in tmp_path.iterdir() if p.suffix in (".html", ".pdf")]
    assert rendered, "no report file written"
    html_files = [p for p in rendered if p.suffix == ".html"]
    if html_files:  # WeasyPrint absent on Windows dev — HTML fallback
        content = html_files[0].read_text(encoding="utf-8")
        assert "Allocation Statement" in content
        assert "PO-R" in content
        assert "default factors" in content
        assert "Rework Rate" in content


def test_buyer_share_link_public(client):
    """Read-only share link works without auth and shows the same payload."""
    product_id = _make_product(client, "TEE-07", 200, 20)
    order = _make_order(client, "PO-H", product_id, 500)
    batch = _make_batch(client, "LOT-7", 200, inputs=[
        {"input_type": "water_l", "quantity": 2000},
    ])
    client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order["id"], "fabric_kg": 200},
    ]})

    token = client.post(f"/api/orders/{order['id']}/share-link").json()["share_token"]
    assert token

    public = client.get(f"/api/share/{token}")
    assert public.status_code == 200
    body = public.json()
    assert body["order_code"] == "PO-H"
    assert body["water_l"] == pytest.approx(2000)
    assert "quality_mix" in body

    assert client.get("/api/share/not-a-real-token").status_code == 404
