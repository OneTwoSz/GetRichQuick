"""
Seed a demo factory with realistic Tiruppur-scale data.

Run inside the backend container:
    docker-compose exec backend python -m app.jobs.seed_demo

Idempotent: re-running upserts the same demo user/factory rather than
creating duplicates.

Demo credentials:
    email:    demo@greenthread.app
    password: demo1234
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from ..database import SessionLocal, init_db
from ..models import (
    BatchAllocation,
    BatchInput,
    BatchInputType,
    BillOfMaterialsItem,
    Chemical,
    DataQuality,
    FabricInventory,
    Factory,
    FabricType,
    JobWorker,
    MaterialCategory,
    MonthlyUtility,
    Order,
    OrderStatus,
    ProcessType,
    Product,
    ProductionBatch,
    ProductionRecord,
    ProductLifecycle,
    ProductPassport,
    ProductSupplier,
    STAGE_TIER,
    Supplier,
    SupplierDataRequest,
    SupplierSubmission,
    SupplyChainStage,
    TransportMode,
    User,
    UserRole,
)
from ..services import batch_carbon
from ..services import passport as passport_service
from ..services.allocation import AllocationLine, compute_shares, fabric_demand_kg
from ..utils.auth import get_password_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("seed_demo")

DEMO_EMAIL = "demo@greenthread.app"
DEMO_PASSWORD = "demo1234"
DEMO_NAME = "Karthik Selvam"
DEMO_FACTORY = "Saravana Knits Pvt Ltd"
DEMO_LOCATION = "Tiruppur, Tamil Nadu"


def main() -> int:
    # Make the script standalone: create tables if the DB is fresh. In the
    # uvicorn flow this already happens on startup, but seed_demo is the
    # first thing a new contributor runs (before the server is up), so it
    # owns table creation when DATABASE_URL points at an empty file.
    init_db()

    db = SessionLocal()
    try:
        random.seed(42)  # deterministic numbers across runs

        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if user is None:
            user = User(
                email=DEMO_EMAIL,
                password_hash=get_password_hash(DEMO_PASSWORD),
                name=DEMO_NAME,
                role=UserRole.FACTORY_MANAGER,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("created demo user %s", DEMO_EMAIL)
        else:
            # Reset password in case the schema/hash changed.
            user.password_hash = get_password_hash(DEMO_PASSWORD)
            db.commit()
            logger.info("demo user already exists; reset password")

        factory = db.query(Factory).filter(Factory.user_id == user.id).first()
        if factory is None:
            factory = Factory(
                user_id=user.id,
                name=DEMO_FACTORY,
                location=DEMO_LOCATION,
                gst_number="33ABCDE1234F1Z5",
                employee_count=120,
                production_capacity_kg_per_month=18000,
            )
            db.add(factory)
            db.commit()
            db.refresh(factory)
            logger.info("created demo factory %s", DEMO_FACTORY)

        # Production records — last 90 days, ~3 per week.
        existing_records = (
            db.query(ProductionRecord).filter(ProductionRecord.factory_id == factory.id).count()
        )
        if existing_records == 0:
            today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
            fabrics = [FabricType.COTTON, FabricType.ORGANIC_COTTON, FabricType.BLEND, FabricType.POLYESTER]
            for days_ago in range(0, 90, 2):  # every other day
                date = today - timedelta(days=days_ago)
                fabric_type = random.choice(fabrics)
                fabric_kg = random.uniform(180, 420)
                garments = int(fabric_kg * random.uniform(3.0, 4.5))  # ~250-400 g/garment
                rec = ProductionRecord(
                    factory_id=factory.id,
                    date=date,
                    fabric_type=fabric_type,
                    fabric_quantity_kg=round(fabric_kg, 2),
                    dye_quantity_kg=round(fabric_kg * random.uniform(0.04, 0.06), 2),
                    chemicals_kg=round(fabric_kg * random.uniform(0.02, 0.03), 2),
                    electricity_kwh=round(fabric_kg * random.uniform(2.5, 3.4), 2),
                    water_liters=round(fabric_kg * random.uniform(70, 95), 2),
                    wastewater_treated_liters=round(fabric_kg * random.uniform(60, 85), 2),
                    garments_produced=garments,
                    transport_distance_km=random.choice([0, 0, 14, 28, 45, 120]),
                    transport_mode=random.choice([None, TransportMode.TRUCK, TransportMode.TRUCK]),
                    notes=None,
                    created_by=user.id,
                )
                db.add(rec)
            db.commit()
            logger.info("seeded ~%d production records", 90 // 2)
        else:
            logger.info("production records already present (%d) — skipping", existing_records)

        # Products — three styles a typical Tiruppur knit unit makes for EU
        # buyers. BOMs are lightweight but realistic per-garment inputs.
        if db.query(Product).filter(Product.factory_id == factory.id).count() == 0:
            product_specs = [
                {
                    "sku": "GTW-CT-180",
                    "name": "Crew Tee (Conventional Cotton, 180 GSM)",
                    "description": "Workhorse short-sleeve crew tee, conventional cotton single jersey.",
                    "fiber_composition": "100% cotton",
                    "garment_weight_g": 220.0,
                    "recycled_content_pct": 0,
                    "care_instructions": "Machine wash cold, tumble dry low.",
                    "target_buyer": "C&A Germany",
                    "bom": [
                        ("Cotton single jersey 180 GSM", MaterialCategory.FIBER, "cotton", 220.0, None),
                        ("Reactive dye blend", MaterialCategory.DYE, "reactive_dye", 9.0, None),
                        ("Sodium carbonate", MaterialCategory.CHEMICAL, "sodium_carbonate", 18.0, None),
                        ("Glauber salt", MaterialCategory.CHEMICAL, "glauber_salt", 25.0, None),
                        ("Sewing thread", MaterialCategory.TRIM, "sewing_thread", 3.0, None),
                        ("Care label", MaterialCategory.TRIM, "label", 1.5, None),
                    ],
                },
                {
                    "sku": "GTW-OC-200",
                    "name": "Oversized Tee (Organic Cotton, 200 GSM)",
                    "description": "GOTS-certified organic cotton boxy fit for premium EU buyers.",
                    "fiber_composition": "100% organic cotton (GOTS)",
                    "garment_weight_g": 260.0,
                    "recycled_content_pct": 0,
                    "care_instructions": "Machine wash cold, line dry. GOTS certified.",
                    "target_buyer": "Armedangels",
                    "bom": [
                        ("Organic cotton jersey 200 GSM", MaterialCategory.FIBER, "organic_cotton", 260.0, None),
                        ("Low-impact reactive dye", MaterialCategory.DYE, "reactive_dye", 8.0, 3.5),  # supplier override
                        ("Soda ash", MaterialCategory.CHEMICAL, "sodium_carbonate", 20.0, None),
                        ("GOTS softener", MaterialCategory.CHEMICAL, "softener", 5.0, None),
                        ("Sewing thread", MaterialCategory.TRIM, "sewing_thread", 3.5, None),
                        ("Woven label", MaterialCategory.TRIM, "label", 1.8, None),
                    ],
                },
                {
                    "sku": "GTW-RPC-220",
                    "name": "Performance Polo (Recycled PET / Cotton Blend)",
                    "description": "Pique knit polo, 50/50 recycled polyester and cotton.",
                    "fiber_composition": "50% recycled polyester, 50% cotton",
                    "garment_weight_g": 240.0,
                    "recycled_content_pct": 50,
                    "care_instructions": "Machine wash warm, do not bleach.",
                    "target_buyer": "H&M Group",
                    "bom": [
                        ("Recycled polyester yarn", MaterialCategory.FIBER, "recycled_polyester", 120.0, None),
                        ("Combed cotton yarn", MaterialCategory.FIBER, "cotton", 120.0, None),
                        ("Disperse dye (poly side)", MaterialCategory.DYE, "disperse_dye", 6.0, None),
                        ("Reactive dye (cotton side)", MaterialCategory.DYE, "reactive_dye", 6.0, None),
                        ("Caustic soda", MaterialCategory.CHEMICAL, "caustic_soda", 8.0, None),
                        ("Polyester buttons (3)", MaterialCategory.TRIM, "button", 4.5, None),
                        ("Sewing thread", MaterialCategory.TRIM, "sewing_thread", 3.5, None),
                        ("Recycled label", MaterialCategory.TRIM, "label", 1.5, None),
                    ],
                },
            ]
            seeded_products: list[Product] = []
            for spec in product_specs:
                product = Product(
                    factory_id=factory.id,
                    sku=spec["sku"],
                    name=spec["name"],
                    description=spec["description"],
                    fiber_composition=spec["fiber_composition"],
                    garment_weight_g=spec["garment_weight_g"],
                    recycled_content_pct=spec["recycled_content_pct"],
                    care_instructions=spec["care_instructions"],
                    target_buyer=spec["target_buyer"],
                    active=True,
                )
                db.add(product)
                db.flush()
                for name, category, key, qty_g, override in spec["bom"]:
                    db.add(BillOfMaterialsItem(
                        product_id=product.id,
                        material_name=name,
                        category=category,
                        material_key=key,
                        quantity_per_garment_g=qty_g,
                        carbon_factor_override=override,
                    ))
                seeded_products.append(product)
            db.commit()
            logger.info("seeded %d products", len(seeded_products))

            # Link existing production batches to products by fabric type
            # so per-SKU "actual" rollups have data on first boot.
            fabric_to_sku = {
                FabricType.COTTON: "GTW-CT-180",
                FabricType.ORGANIC_COTTON: "GTW-OC-200",
                FabricType.BLEND: "GTW-RPC-220",
                FabricType.POLYESTER: "GTW-RPC-220",
            }
            sku_to_id = {p.sku: p.id for p in seeded_products}
            linked = 0
            for record in db.query(ProductionRecord).filter(
                ProductionRecord.factory_id == factory.id,
                ProductionRecord.product_id.is_(None),
            ).all():
                target_sku = fabric_to_sku.get(record.fabric_type)
                if target_sku:
                    record.product_id = sku_to_id[target_sku]
                    linked += 1
            db.commit()
            logger.info("linked %d production records to products", linked)

        # Chemicals — a handful of typical Tiruppur dyehouse entries.
        if db.query(Chemical).filter(Chemical.factory_id == factory.id).count() == 0:
            chemicals = [
                # (name, supplier, qty_kg, cas, reach, zdhc)
                ("Reactive Red 195", "Atul Ltd", 240.0, "93050-79-4", True, True),
                ("Reactive Blue 21", "Colourtex", 180.0, "12236-86-1", True, True),
                ("Sodium Carbonate", "Tata Chemicals", 1200.0, "497-19-8", True, True),
                ("Glauber Salt", "Local supplier", 1500.0, "7727-73-3", True, True),
                ("Acid Black 1", "Indokem", 90.0, "1064-48-8", True, False),  # ZDHC needs review
                ("Caustic Soda Flakes", "Grasim", 600.0, "1310-73-2", True, True),
            ]
            for name, supplier, qty, cas, reach, zdhc in chemicals:
                db.add(Chemical(
                    factory_id=factory.id,
                    chemical_name=name,
                    supplier=supplier,
                    quantity_kg=qty,
                    cas_number=cas,
                    reach_compliant=reach,
                    zdhc_compliant=zdhc,
                ))
            db.commit()
            logger.info("seeded %d chemicals", len(chemicals))

        # ------------------------------------------------------------------
        # Phase 2 — batches, orders, allocation. Shows the whole story on
        # first login: a shared dye lot split across two orders, a rework
        # run, an outsourced lot on default factors, leftover fabric in
        # stock, and a monthly utility entry so reconciliation has data.
        # ------------------------------------------------------------------
        if db.query(ProductionBatch).filter(ProductionBatch.factory_id == factory.id).count() == 0:
            products = {
                p.sku: p
                for p in db.query(Product).filter(Product.factory_id == factory.id).all()
            }
            # Realistic knitwear cutting waste per style (used to compute
            # each order's fabric demand incl. waste).
            for sku, waste in (("GTW-CT-180", 18.0), ("GTW-OC-200", 20.0), ("GTW-RPC-220", 22.0)):
                if sku in products and not products[sku].cutting_waste_percent:
                    products[sku].cutting_waste_percent = waste
            db.commit()

            orders_spec = [
                ("PO-2026-101", "C&A Germany", "GTW-CT-180", 3000, None),
                ("PO-2026-102", "Armedangels", "GTW-OC-200", 2000, None),
                ("PO-2026-103", "H&M Group", "GTW-RPC-220", 1500, 1_850_000.0),
            ]
            orders: dict[str, Order] = {}
            for code, buyer, sku, units, value in orders_spec:
                order = Order(
                    factory_id=factory.id,
                    order_code=code,
                    buyer_name=buyer,
                    product_id=products[sku].id,
                    units=units,
                    order_value=value,
                    status=OrderStatus.IN_PRODUCTION,
                    created_by=user.id,
                )
                db.add(order)
                orders[code] = order
            db.commit()
            logger.info("seeded %d orders", len(orders))

            dye_house = JobWorker(
                factory_id=factory.id,
                name="Sakthi Dyeing Works",
                process_type=ProcessType.DYEING,
                location="SIPCOT, Perundurai",
                contact="+91 98430 00000",
            )
            db.add(dye_house)
            db.commit()

            now = datetime.now(timezone.utc)

            def demand(code: str) -> float:
                order = orders[code]
                product = db.get(Product, order.product_id)
                return round(fabric_demand_kg(
                    order.units, product.garment_weight_g / 1000.0, product.cutting_waste_percent
                ), 1)

            # 1. In-house dye lot shared by two orders + a ~3% buffer.
            kg_101 = demand("PO-2026-101")   # ≈ 805 kg
            kg_102 = demand("PO-2026-102")   # ≈ 650 kg
            lot_size = round((kg_101 + kg_102) * 1.03, 0)
            shared = ProductionBatch(
                factory_id=factory.id,
                batch_code="LOT-2026-0701-WHT",
                process_type=ProcessType.DYEING,
                colour="white",
                started_at=now - timedelta(days=8),
                total_fabric_kg=lot_size,
                allocation_note="Combined white run for PO-101 + PO-102 (same fabric, one dye bath).",
                created_by=user.id,
            )
            db.add(shared)
            db.flush()
            for input_type, qty, quality, source in [
                (BatchInputType.WATER_L, lot_size * 95, DataQuality.MEASURED, "borewell flow meter"),
                (BatchInputType.ELECTRICITY_KWH, lot_size * 1.1, DataQuality.MEASURED, "sub-meter, dye house"),
                (BatchInputType.CHEMICAL_KG, lot_size * 0.5, DataQuality.ESTIMATED, "recipe sheet"),
                (BatchInputType.DYE_KG, lot_size * 0.03, DataQuality.MEASURED, "weighed drawdown"),
                (BatchInputType.STEAM_KG, lot_size * 2.0, DataQuality.ESTIMATED, "boiler log"),
            ]:
                db.add(BatchInput(
                    batch_id=shared.id, input_type=input_type,
                    quantity=round(qty, 1), data_quality=quality, source=source,
                ))
            db.flush()

            result = compute_shares(lot_size, [
                AllocationLine(order_id=orders["PO-2026-101"].id, fabric_kg=kg_101,
                               garment_units=orders["PO-2026-101"].units),
                AllocationLine(order_id=orders["PO-2026-102"].id, fabric_kg=kg_102,
                               garment_units=orders["PO-2026-102"].units),
            ])
            for line_kg, code in ((kg_101, "PO-2026-101"), (kg_102, "PO-2026-102")):
                order = orders[code]
                db.add(BatchAllocation(
                    batch_id=shared.id, order_id=order.id, product_id=order.product_id,
                    fabric_kg=line_kg, garment_units=order.units,
                    allocated_share=result.shares[order.id],
                ))
            db.flush()

            # 2. Rework: part of the white lot failed shade matching.
            rework = ProductionBatch(
                factory_id=factory.id,
                batch_code="LOT-2026-0701-WHT-RW1",
                process_type=ProcessType.DYEING,
                colour="white (re-dye)",
                started_at=now - timedelta(days=5),
                total_fabric_kg=round(lot_size * 0.2, 0),
                is_rework=True,
                rework_of_batch_id=shared.id,
                allocation_note="Shade mismatch on ~20% of the lot; re-dyed.",
                created_by=user.id,
            )
            db.add(rework)
            db.flush()
            for input_type, qty in [
                (BatchInputType.WATER_L, lot_size * 0.2 * 95),
                (BatchInputType.ELECTRICITY_KWH, lot_size * 0.2 * 1.1),
                (BatchInputType.CHEMICAL_KG, lot_size * 0.2 * 0.5),
            ]:
                db.add(BatchInput(
                    batch_id=rework.id, input_type=input_type,
                    quantity=round(qty, 1), data_quality=DataQuality.MEASURED,
                    source="re-dye run",
                ))

            # 3. Outsourced navy lot at the job worker — no primary data
            #    yet, so it runs on built-in default factors until the dye
            #    house submits actuals through the token link.
            kg_103 = demand("PO-2026-103")
            outsourced = ProductionBatch(
                factory_id=factory.id,
                batch_code="LOT-2026-0705-NVY",
                process_type=ProcessType.DYEING,
                colour="navy",
                started_at=now - timedelta(days=4),
                total_fabric_kg=round(kg_103 * 1.04, 0),
                outsourced=True,
                job_worker_id=dye_house.id,
                job_work_token="demo-jobwork-token",
                allocation_note="Job-worked at Sakthi Dyeing; awaiting their consumption figures.",
                created_by=user.id,
            )
            db.add(outsourced)
            db.flush()
            out_result = compute_shares(outsourced.total_fabric_kg, [
                AllocationLine(order_id=orders["PO-2026-103"].id, fabric_kg=kg_103,
                               garment_units=orders["PO-2026-103"].units,
                               order_value=orders["PO-2026-103"].order_value),
            ])
            db.add(BatchAllocation(
                batch_id=outsourced.id, order_id=orders["PO-2026-103"].id,
                product_id=orders["PO-2026-103"].product_id,
                fabric_kg=kg_103, garment_units=orders["PO-2026-103"].units,
                order_value=orders["PO-2026-103"].order_value,
                allocated_share=out_result.shares[orders["PO-2026-103"].id],
            ))
            db.commit()

            # Complete the shared lot → leftover buffer flows to inventory
            # with its pro-rata embodied footprint (incl. the rework run).
            shared.completed_at = now - timedelta(days=3)
            stored = batch_carbon.stored_allocation_result(shared)
            if stored.leftover_fabric_kg > 0:
                totals = batch_carbon.batch_totals(shared)
                rework_totals = batch_carbon.batch_totals(rework)
                db.add(FabricInventory(
                    factory_id=factory.id,
                    source_batch_id=shared.id,
                    fabric_kg=round(stored.leftover_fabric_kg, 1),
                    embodied_co2_kg=round((totals.co2_kg + rework_totals.co2_kg) * stored.leftover_share, 2),
                    embodied_water_l=round((totals.water_l + rework_totals.water_l) * stored.leftover_share, 1),
                ))
            db.commit()

            # 4. Monthly utility bill for the shared lot's month, sized so
            #    reconciliation shows a believable facility overhead above
            #    the batch-attributed inputs.
            month_anchor = shared.started_at
            db.add(MonthlyUtility(
                factory_id=factory.id,
                year=month_anchor.year,
                month=month_anchor.month,
                total_electricity_kwh=round(lot_size * 1.1 * 1.6, 0),
                total_water_liters=round(lot_size * 95 * 1.25, 0),
                note="EB + borewell bill totals (demo)",
            ))
            db.commit()
            logger.info("seeded phase-2 batches, allocations, inventory, utilities")
        else:
            logger.info("production batches already present — skipping phase-2 seed")

        # Phase 3 — supply chain, supplier primary data, life-cycle
        # settings, and one published passport.
        if db.query(Supplier).filter(Supplier.factory_id == factory.id).count() == 0:
            _seed_phase3(db, factory, user)
            logger.info("seeded phase-3 suppliers, life-cycle settings and passport")
        else:
            logger.info("suppliers already present — skipping phase-3 seed")

        logger.info("done. login at /login with %s / %s", DEMO_EMAIL, DEMO_PASSWORD)
        return 0
    finally:
        db.close()


def _seed_phase3(db, factory: Factory, user: User) -> None:
    specs = [
        # name, stage, city, certifications
        ("Vidarbha Organic Cotton Collective", SupplyChainStage.RAW_MATERIALS, "Akola", ["GOTS"]),
        ("Gujarat PET Recyclers", SupplyChainStage.RAW_MATERIALS, "Surat", ["GRS"]),
        ("Kovai Organic Spinners", SupplyChainStage.YARN_PRODUCTION, "Coimbatore", ["GOTS", "OEKO-TEX"]),
        ("Sri Murugan Knit Fabrics", SupplyChainStage.FABRIC_PRODUCTION, "Tiruppur", ["OEKO-TEX"]),
        ("Sakthi Dyeing", SupplyChainStage.WET_PROCESSING, "Tiruppur", ["ZDHC Wastewater"]),
    ]
    suppliers = {}
    for name, stage, city, certs in specs:
        s = Supplier(factory_id=factory.id, name=name, stage=stage, tier=STAGE_TIER[stage],
                     country="IN", city=city, certifications=[{"name": c} for c in certs])
        db.add(s)
        suppliers[name] = s
    db.flush()

    # The spinner has submitted metered data; the knit mill has a pending
    # request at a stable demo URL (/supplier-data/demo-supplier-token).
    spinner, mill = suppliers["Kovai Organic Spinners"], suppliers["Sri Murugan Knit Fabrics"]
    spin_req = SupplierDataRequest(factory_id=factory.id, supplier_id=spinner.id,
                                   stage=spinner.stage, token="demo-spinner-token",
                                   period_label="Apr–Jun 2026", created_by=user.id)
    db.add(spin_req)
    db.add(SupplierDataRequest(factory_id=factory.id, supplier_id=mill.id, stage=mill.stage,
                               token="demo-supplier-token", period_label="Apr–Jun 2026",
                               created_by=user.id))
    db.flush()
    db.add(SupplierSubmission(
        request_id=spin_req.id, supplier_id=spinner.id, stage=spinner.stage,
        period_label="Apr–Jun 2026", output_kg=180000, electricity_kwh=594000,
        water_l=90000, data_quality=DataQuality.MEASURED, submitted_by="Mill engineer",
    ))

    products = {p.sku: p for p in db.query(Product).filter(Product.factory_id == factory.id).all()}
    links = {
        "GTW-OC-200": ["Vidarbha Organic Cotton Collective", "Kovai Organic Spinners",
                       "Sri Murugan Knit Fabrics", "Sakthi Dyeing"],
        "GTW-CT-180": ["Kovai Organic Spinners", "Sri Murugan Knit Fabrics"],
        "GTW-RPC-220": ["Gujarat PET Recyclers"],
    }
    for sku, names in links.items():
        if sku not in products:
            continue
        for name in names:
            s = suppliers[name]
            db.add(ProductSupplier(product_id=products[sku].id, supplier_id=s.id, stage=s.stage))

    # Tiruppur → Chennai port by truck, Chennai → Hamburg by sea, then a
    # last leg to the buyer's DC.
    export_route = [
        {"mode": "truck", "distance_km": 450},
        {"mode": "sea_freight", "distance_km": 15000},
        {"mode": "truck", "distance_km": 300},
    ]
    settings_by_sku = {
        "GTW-OC-200": dict(boundary="cradle_to_grave", washes=50, use_country="DE",
                           packaging=[{"material_key": "recycled_ldpe_polybag", "grams": 8}]),
        "GTW-CT-180": dict(boundary="cradle_to_customer",
                           packaging=[{"material_key": "ldpe_polybag", "grams": 8}]),
    }
    for sku, cfg in settings_by_sku.items():
        if sku in products:
            db.add(ProductLifecycle(product_id=products[sku].id, distribution=export_route, **cfg))
    db.commit()

    if "GTW-OC-200" in products:
        try:
            v = passport_service.publish(
                db, products["GTW-OC-200"], user, reviewed_by=DEMO_NAME,
                review_note="Demo passport — reviewed against Q2 bills and spinner submission.",
            )
            token = db.query(ProductPassport).filter(ProductPassport.id == v.passport_id).first().public_token
            logger.info("published demo passport v%d at /passport/%s", v.version, token)
        except passport_service.PublishBlocked as exc:
            logger.warning("demo passport not published: %s", [i.message for i in exc.issues])


if __name__ == "__main__":
    raise SystemExit(main())
