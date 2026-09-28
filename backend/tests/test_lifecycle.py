"""
Pure life-cycle engine tests — no database. Pins the mass flow, the data
hierarchy (factory primary > supplier primary > declared > default), the
system boundaries and the primary-data share.
"""
import pytest

from app.models import DataQuality
from app.services import lifecycle as lc
from app.utils import factor_library as fl


def _tee(**extra):
    """200 g, 100% conventional cotton tee with 20% cutting waste."""
    return lc.LifecycleInputs(
        garment_weight_g=200, cutting_waste_percent=20,
        fibres=[lc.FibreLine("cotton", 200)], **extra,
    )


def _stage(result, key):
    return next(s for s in result.stages if s.stage == key)


def test_mass_flow_runs_back_through_losses():
    flow = lc.mass_flow(_tee())
    assert flow["fabric_kg"] == pytest.approx(0.25)
    assert flow["yarn_kg"] == pytest.approx(0.25 / 0.98)
    assert flow["fibre_kg_total"] == pytest.approx(0.25 / 0.98 / 0.88)


def test_all_default_cradle_to_gate():
    r = lc.compute(_tee())
    assert [s.stage for s in r.stages] == [
        "raw_materials", "yarn_production", "fabric_production",
        "wet_processing", "assembly", "trims_packaging",
    ]
    assert r.excluded_stages == ["distribution", "use", "end_of_life"]
    assert r.primary_share_pct == 0
    assert r.quality_mix["default_factor"] == pytest.approx(100)
    fibre_kg = 0.25 / 0.98 / 0.88
    assert _stage(r, "raw_materials").co2e_kg == pytest.approx(fibre_kg * 2.0, rel=1e-4)
    # Spinning default: 3.5 kWh/kg yarn at the Indian grid factor.
    assert _stage(r, "yarn_production").co2e_kg == pytest.approx(0.25 / 0.98 * 3.5 * 0.85, rel=1e-4)
    assert r.co2e_kg == pytest.approx(sum(s.co2e_kg for s in r.stages), abs=1e-3)


def test_factory_primary_replaces_default_and_counts_as_primary():
    primary = lc.StageActivity(
        co2e_kg=0.30, water_l=20.0, energy_kwh=0.2,
        quality_amounts={DataQuality.MEASURED: 0.24, DataQuality.ESTIMATED: 0.06},
        source="allocated batch data",
    )
    r = lc.compute(_tee(factory_primary={"wet_processing": primary}))
    wet = _stage(r, "wet_processing")
    assert wet.data_source == "factory_primary"
    assert wet.co2e_kg == pytest.approx(0.30)
    assert wet.quality_mix["measured"] == pytest.approx(80)
    assert r.primary_share_pct == pytest.approx(0.30 / r.co2e_kg * 100, abs=0.05)


def test_supplier_intensity_uses_supplier_country_grid():
    def yarn(country):
        sub = lc.SupplierIntensity({"electricity_kwh": 3.0}, DataQuality.MEASURED,
                                   "spinner", country=country)
        return _stage(lc.compute(_tee(supplier_intensities={"yarn_production": sub})), "yarn_production")

    india, bangladesh = yarn("IN"), yarn("BD")
    assert india.data_source == "supplier_primary"
    assert india.country == "IN"
    assert india.co2e_kg == pytest.approx(0.25 / 0.98 * 3.0 * 0.85, rel=1e-4)
    assert bangladesh.co2e_kg == pytest.approx(0.25 / 0.98 * 3.0 * 0.62, rel=1e-4)


def test_factory_batches_on_default_factors_are_not_primary():
    """An outsourced lot with no submission is factory data, not primary data."""
    defaults = lc.StageActivity(0.3, 25.0, 0.25, {DataQuality.DEFAULT_FACTOR: 0.3}, "outsourced lot")
    r = lc.compute(_tee(factory_primary={"wet_processing": defaults}))
    assert _stage(r, "wet_processing").data_source == "factory_default"
    assert r.primary_share_pct == 0


def test_factory_primary_wins_over_supplier():
    primary = lc.StageActivity(0.1, 0, 0, {DataQuality.MEASURED: 0.1}, "batches")
    sub = lc.SupplierIntensity({"electricity_kwh": 1.0}, DataQuality.ESTIMATED, "mill")
    r = lc.compute(_tee(factory_primary={"fabric_production": primary},
                        supplier_intensities={"fabric_production": sub}))
    assert _stage(r, "fabric_production").data_source == "factory_primary"


def test_supplier_declared_fibre_factor_is_estimated():
    r = lc.compute(lc.LifecycleInputs(
        garment_weight_g=200, fibres=[lc.FibreLine("recycled_polyester", 200, declared_co2e_per_kg=1.1)],
    ))
    raw = _stage(r, "raw_materials")
    assert raw.data_source == "supplier_declared"
    assert raw.quality_mix["estimated"] == pytest.approx(100)


def test_unknown_fibre_is_flagged_not_zero():
    r = lc.compute(lc.LifecycleInputs(garment_weight_g=200, fibres=[lc.FibreLine("hemp_blend", 200)]))
    raw = _stage(r, "raw_materials")
    assert "unknown_fibre:hemp_blend" in raw.flags
    assert raw.co2e_kg > 0


def test_no_fibre_lines_still_charges_raw_materials():
    r = lc.compute(lc.LifecycleInputs(garment_weight_g=200))
    assert _stage(r, "raw_materials").co2e_kg > 0


def test_distribution_per_tonne_km():
    r = lc.compute(_tee(boundary="cradle_to_customer",
                        distribution=[lc.TransportLeg("sea_freight", 10_000)]))
    # 0.2 kg garment, no packaging: 0.0002 t × 10,000 km × 0.016
    assert _stage(r, "distribution").co2e_kg == pytest.approx(0.032)


def test_cradle_to_grave_use_and_end_of_life():
    r = lc.compute(_tee(boundary="cradle_to_grave", washes=50, use_country="EU"))
    use = _stage(r, "use")
    loads = 50 * 0.2 / 4.0
    assert use.energy_kwh == pytest.approx(loads * 0.5)
    assert use.co2e_kg == pytest.approx(loads * 0.5 * 0.25 + loads * 50 * 0.0003, rel=1e-4)
    assert _stage(r, "end_of_life").co2e_kg == pytest.approx(0.2 * 0.8)
    assert r.excluded_stages == []


def test_missing_scenario_data_is_flagged():
    r = lc.compute(_tee(boundary="cradle_to_grave"))
    assert "no_transport_legs" in _stage(r, "distribution").flags
    assert "no_wash_scenario" in _stage(r, "use").flags


def test_trims_and_packaging():
    r = lc.compute(_tee(trims=[lc.MaterialLine("button", 2)],
                        packaging=[lc.MaterialLine("ldpe_polybag", 10)]))
    assert _stage(r, "trims_packaging").co2e_kg == pytest.approx(0.002 * 3.0 + 0.010 * 2.1)


def test_rejects_bad_inputs():
    with pytest.raises(ValueError):
        lc.compute(_tee(boundary="cradle_to_moon"))
    with pytest.raises(ValueError):
        lc.compute(lc.LifecycleInputs(garment_weight_g=0))


def test_factor_library_carries_provenance():
    for table in (fl.FIBRE_FACTORS, fl.GRID_FACTORS, fl.TRANSPORT_FACTORS):
        for f in table.values():
            assert f.source
