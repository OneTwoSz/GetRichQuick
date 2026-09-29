"""
Phase 3 end-to-end: product life-cycle footprint from factory batches and
supplier submissions, validation gates, ecodesign scenarios, and signed
Digital Product Passports (including tamper detection).
"""
import pytest

from app.database import get_db
from app.main import app
from app.models import PassportVersion
from app.utils import factor_library as fl

IN_GRID = fl.GRID_FACTORS["IN"].co2e
WATER = fl.INPUT_FACTORS["water_l"].co2e


def _product(client, sku="TEE-LC", weight=200, waste=20, bom=None):
    r = client.post("/api/products", json={
        "sku": sku, "name": "Crew tee", "garment_weight_g": weight,
        "cutting_waste_percent": waste,
        "bom": bom if bom is not None else [
            {"material_name": "Cotton jersey", "category": "fiber",
             "material_key": "cotton", "quantity_per_garment_g": weight},
            {"material_name": "Reactive dye", "category": "dye",
             "material_key": "reactive_dye", "quantity_per_garment_g": 4},
        ],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _dyed_order(client, product_id, units=1000, code="PO-LC"):
    order = client.post("/api/orders", json={
        "order_code": code, "product_id": product_id, "units": units,
    }).json()
    batch = client.post("/api/batches", json={
        "batch_code": f"LOT-{code}", "process_type": "dyeing", "colour": "navy",
        "started_at": "2026-07-01T08:00:00Z", "total_fabric_kg": 250,
        "inputs": [
            {"input_type": "water_l", "quantity": 20000, "data_quality": "measured"},
            {"input_type": "electricity_kwh", "quantity": 250, "data_quality": "measured"},
        ],
    }).json()
    r = client.post(f"/api/batches/{batch['id']}/allocations", json={"lines": [
        {"order_id": order["id"], "fabric_kg": 250},
    ]})
    assert r.status_code == 200, r.text
    return order


def _stage(fp, key):
    return next(s for s in fp["stages"] if s["stage"] == key)


def test_footprint_uses_factory_batches_for_wet_processing(client):
    pid = _product(client)
    _dyed_order(client, pid)
    fp = client.get(f"/api/products/{pid}/footprint").json()

    wet = _stage(fp, "wet_processing")
    assert wet["data_source"] == "factory_primary"
    # 250 kWh + 20,000 L at the library factors, over 1,000 garments
    assert wet["co2e_kg"] == pytest.approx((250 * IN_GRID + 20000 * WATER) / 1000, rel=1e-3)
    assert wet["water_l"] == pytest.approx(20.0)
    assert wet["quality_mix"]["measured"] == pytest.approx(100)
    assert _stage(fp, "fabric_production")["data_source"] == "default"
    assert fp["primary_share_pct"] > 0
    # The dye BOM line is not double counted as a raw material.
    fibre_kg = 0.25 / 0.98 / 0.88
    assert _stage(fp, "raw_materials")["co2e_kg"] == pytest.approx(fibre_kg * 2.0, rel=1e-3)


def test_supplier_data_link_upgrades_yarn_stage(client):
    pid = _product(client)
    supplier = client.post("/api/suppliers", json={
        "name": "Kovai Spinners", "stage": "yarn_production", "country": "in",
        "city": "Coimbatore", "certifications": [{"name": "GOTS"}],
    }).json()
    assert supplier["tier"] == 3
    assert supplier["country"] == "IN"

    r = client.put(f"/api/products/{pid}/suppliers",
                   json={"stage": "yarn_production", "supplier_id": supplier["id"]})
    assert r.status_code == 200, r.text
    before = _stage(client.get(f"/api/products/{pid}/footprint").json(), "yarn_production")
    assert before["data_source"] == "default"

    req = client.post(f"/api/suppliers/{supplier['id']}/data-requests",
                      json={"period_label": "Apr–Jun 2026"}).json()
    info = client.get(f"/api/supplier-data/{req['token']}").json()
    assert info["stage"] == "yarn_production" and not info["already_submitted"]

    r = client.post(f"/api/supplier-data/{req['token']}", json={
        "output_kg": 100000, "electricity_kwh": 300000, "data_quality": "measured",
        "submitted_by": "Plant manager",
    })
    assert r.status_code == 201, r.text

    after = _stage(client.get(f"/api/products/{pid}/footprint").json(), "yarn_production")
    assert after["data_source"] == "supplier_primary"
    assert after["quality_mix"]["measured"] == pytest.approx(100)
    assert after["co2e_kg"] == pytest.approx(0.25 / 0.98 * 3.0 * IN_GRID, rel=1e-3)
    assert client.get(f"/api/supplier-data/{req['token']}").json()["already_submitted"]


def test_implausible_supplier_submission_blocks_publishing(client):
    pid = _product(client)
    s = client.post("/api/suppliers", json={"name": "Mill", "stage": "fabric_production"}).json()
    client.put(f"/api/products/{pid}/suppliers", json={"stage": "fabric_production", "supplier_id": s["id"]})
    token = client.post(f"/api/suppliers/{s['id']}/data-requests", json={}).json()["token"]
    # kWh typed as Wh: 1,000 kWh per kg of fabric
    client.post(f"/api/supplier-data/{token}", json={"output_kg": 10, "electricity_kwh": 10000})

    v = client.get(f"/api/products/{pid}/validation").json()
    assert not v["publishable"]
    assert any(i["code"] == "intensity_implausible" for i in v["issues"])

    r = client.post(f"/api/products/{pid}/passport/publish", json={"reviewed_by_name": "R. Kumar"})
    assert r.status_code == 422
    assert r.json()["detail"]["issues"]


def test_fibre_heavier_than_garment_is_an_error(client):
    pid = _product(client, bom=[{"material_name": "Cotton", "category": "fiber",
                                 "material_key": "cotton", "quantity_per_garment_g": 400}])
    v = client.get(f"/api/products/{pid}/validation").json()
    assert any(i["code"] == "fibre_exceeds_garment" and i["severity"] == "error" for i in v["issues"])


def test_scenario_organic_cotton_lowers_footprint(client):
    pid = _product(client)
    r = client.post(f"/api/products/{pid}/footprint/scenario",
                    json={"fibre_swaps": {"cotton": "organic_cotton"}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["delta_co2e_kg"] < 0
    assert _stage(body["scenario"], "raw_materials")["co2e_kg"] < _stage(body["baseline"], "raw_materials")["co2e_kg"]


def test_lifecycle_settings_round_trip_and_boundary(client):
    pid = _product(client)
    r = client.put(f"/api/products/{pid}/lifecycle", json={
        "boundary": "cradle_to_grave",
        "packaging": [{"material_key": "ldpe_polybag", "grams": 8}],
        "distribution": [{"mode": "truck", "distance_km": 450}, {"mode": "sea_freight", "distance_km": 14000}],
        "washes": 40, "use_country": "de",
    })
    assert r.status_code == 200, r.text
    assert r.json()["use_country"] == "DE"
    fp = client.get(f"/api/products/{pid}/footprint").json()
    assert fp["boundary"] == "cradle_to_grave"
    assert {"distribution", "use", "end_of_life"} <= {s["stage"] for s in fp["stages"]}
    assert _stage(fp, "use")["country"] == "DE"
    # Query-string override narrows the boundary without saving it.
    gate = client.get(f"/api/products/{pid}/footprint?boundary=cradle_to_gate").json()
    assert "use" in gate["excluded_stages"]


def test_publish_passport_signed_public_and_tamper_evident(client):
    pid = _product(client)
    _dyed_order(client, pid)
    spinner = client.post("/api/suppliers", json={
        "name": "Secret Spinning Co", "stage": "yarn_production", "city": "Coimbatore",
        "certifications": [{"name": "GOTS", "number": "CU-123"}],
    }).json()
    client.put(f"/api/products/{pid}/suppliers", json={"stage": "yarn_production", "supplier_id": spinner["id"]})

    assert client.get(f"/api/products/{pid}/passport").json()["public_token"] is None
    r = client.post(f"/api/products/{pid}/passport/publish",
                    json={"reviewed_by_name": "R. Kumar", "review_note": "Checked July bills"})
    assert r.status_code == 201, r.text
    status = r.json()
    token = status["public_token"]
    assert [v["version"] for v in status["versions"]] == [1]

    pub = client.get(f"/api/passport/{token}").json()
    assert pub["verification"]["verified"] is True
    payload = pub["payload"]
    assert payload["schema"] == "greenthread.dpp/v1"
    assert payload["footprint"]["primary_data_share_pct"] > 0
    assert payload["verification"]["reviewed_by"] == "R. Kumar"
    yarn = next(s for s in payload["supply_chain"] if s["stage"] == "yarn_production")
    assert yarn["facility"] is None            # names withheld by default
    assert yarn["certifications"] == ["GOTS"]
    assert yarn["tier"] == 3

    # A second publish makes an immutable v2; v1 stays readable.
    client.post(f"/api/products/{pid}/passport/publish",
                json={"reviewed_by_name": "R. Kumar", "disclose_supplier_names": True})
    latest = client.get(f"/api/passport/{token}").json()
    assert latest["version"] == 2
    assert any(s.get("facility") == "Secret Spinning Co" for s in latest["payload"]["supply_chain"])
    assert client.get(f"/api/passport/{token}?version=1").json()["version"] == 1

    # Editing the stored payload behind the factory's back breaks verification.
    session = next(app.dependency_overrides[get_db]())  # the client's session
    row = session.query(PassportVersion).filter(PassportVersion.version == 1).first()
    tampered = dict(row.payload)
    tampered["footprint"] = {**tampered["footprint"], "co2e_kg": 0.01}
    row.payload = tampered
    session.commit()
    check = client.get(f"/api/passport/{token}?version=1").json()["verification"]
    assert check["hash_matches"] is False
    assert check["verified"] is False

    qr = client.get(f"/api/passport/{token}/qr.svg")
    assert qr.status_code == 200
    assert qr.headers["content-type"].startswith("image/svg+xml")
    assert 'xmlns="http://www.w3.org/2000/svg"' in qr.text  # renders in <img>
    assert pub["published_at"].endswith(("Z", "+00:00"))    # explicit UTC


def test_unknown_passport_404(client):
    assert client.get("/api/passport/nope").status_code == 404
    assert client.get("/api/passport/nope/qr.svg").status_code == 404


# --- passport presentation: photo, care symbols, label QR ---------------------------

PNG_BYTES = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 64  # signature is what's checked


def test_product_photo_upload_is_hashed_into_passport(client, tmp_path, monkeypatch):
    import hashlib
    from app.config import settings
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    pid = _product(client)

    bad = client.post(f"/api/products/{pid}/image",
                      files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 400  # content sniffed, not trusted from the client

    r = client.post(f"/api/products/{pid}/image", files={"file": ("tee.png", PNG_BYTES, "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["image_url"]
    assert url.startswith("/api/media/") and url.endswith(".png")
    assert client.get(url).content == PNG_BYTES
    assert client.get("/api/media/..%2Fsecret").status_code == 404

    client.post(f"/api/products/{pid}/passport/publish", json={"reviewed_by_name": "R. Kumar"})
    token = client.get(f"/api/products/{pid}/passport").json()["public_token"]
    product = client.get(f"/api/passport/{token}").json()["payload"]["product"]
    assert product["image_url"] == url
    assert product["image_sha256"] == hashlib.sha256(PNG_BYTES).hexdigest()

    # Replacing the photo removes the old file.
    old_file = tmp_path / url.rsplit("/", 1)[-1]
    client.post(f"/api/products/{pid}/image", files={"file": ("b.png", PNG_BYTES + b"1", "image/png")})
    assert not old_file.exists()
    assert client.delete(f"/api/products/{pid}/image").json()["image_url"] is None


def test_care_symbols_one_per_category(client):
    pid = _product(client)
    r = client.put(f"/api/products/{pid}/care-symbols",
                   json={"symbols": ["iron_medium", "wash_30", "do_not_bleach"]})
    assert r.status_code == 200, r.text
    assert r.json()["care_symbols"] == ["wash_30", "do_not_bleach", "iron_medium"]  # label order

    assert client.put(f"/api/products/{pid}/care-symbols",
                      json={"symbols": ["wash_30", "wash_40"]}).status_code == 400
    assert client.put(f"/api/products/{pid}/care-symbols",
                      json={"symbols": ["wash_boiling"]}).status_code == 400

    client.post(f"/api/products/{pid}/passport/publish", json={"reviewed_by_name": "R. Kumar"})
    token = client.get(f"/api/products/{pid}/passport").json()["public_token"]
    symbols = client.get(f"/api/passport/{token}").json()["payload"]["product"]["care_symbols"]
    assert symbols[0] == {"code": "wash_30", "category": "washing", "label": "Machine wash 30°C"}


def test_label_grade_qr(client):
    pid = _product(client)
    client.post(f"/api/products/{pid}/passport/publish", json={"reviewed_by_name": "R. Kumar"})
    token = client.get(f"/api/products/{pid}/passport").json()["public_token"]
    assert client.get(f"/api/passport/{token}/qr.svg?ecc=q").status_code == 200
    assert client.get(f"/api/passport/{token}/qr.svg?ecc=z").status_code == 422


def test_add_missing_columns_upgrades_old_databases():
    from sqlalchemy import create_engine, inspect
    from app.database import add_missing_columns

    old = create_engine("sqlite://")
    with old.begin() as conn:  # a products table from before the photo columns
        conn.exec_driver_sql(
            "CREATE TABLE products (id INTEGER PRIMARY KEY, factory_id INTEGER, sku VARCHAR, "
            "name VARCHAR, garment_weight_g FLOAT, cutting_waste_percent FLOAT, active BOOLEAN)")
    added = add_missing_columns(old)
    assert {"products.image_url", "products.image_sha256", "products.care_symbols"} <= set(added)
    assert "image_url" in {c["name"] for c in inspect(old).get_columns("products")}
    assert add_missing_columns(old) == []  # idempotent
