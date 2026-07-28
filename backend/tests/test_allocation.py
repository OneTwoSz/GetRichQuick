"""
Acceptance tests from GREENTHREAD_PHASE2_SPEC.md §10, pinned against the
pure allocation engine. No database — the engine is deterministic and
I/O-free by design.
"""
import pytest

from app.models import AllocationMethod, DataQuality
from app.services.allocation import (
    AllocationLine,
    MassPoint,
    QualityContribution,
    allocate_quantity,
    compute_shares,
    data_quality_mix,
    fabric_demand_kg,
    leftover_quantity,
    rework_allocation,
    spread_overhead,
)


def test_mass_allocation_600_400():
    """Batch of 1,000 kg serving Order A (600 kg incl. waste) and Order B
    (400 kg): 10,000 L water allocates 6,000 / 4,000. Shares sum to 1.0."""
    result = compute_shares(
        1000,
        [AllocationLine(order_id=1, fabric_kg=600), AllocationLine(order_id=2, fabric_kg=400)],
    )
    water = allocate_quantity(10_000, result)
    assert water[1] == pytest.approx(6_000)
    assert water[2] == pytest.approx(4_000)
    assert sum(result.shares.values()) + result.leftover_share == 1.0  # exactly
    assert result.leftover_share == 0.0


def test_unallocated_fabric_flows_to_inventory():
    """Same batch with 50 kg unallocated → inventory row with 5% of the
    batch footprint; orders stay charged at batch intensity for their own
    kg (Order A's total unchanged), nothing vanishes."""
    result = compute_shares(
        1000,
        [AllocationLine(order_id=1, fabric_kg=600), AllocationLine(order_id=2, fabric_kg=350)],
    )
    assert result.leftover_share == pytest.approx(0.05)
    assert result.leftover_fabric_kg == pytest.approx(50)

    water = allocate_quantity(10_000, result)
    assert water[1] == pytest.approx(6_000)  # unchanged vs fully-allocated batch
    assert leftover_quantity(10_000, result) == pytest.approx(500)
    # Conservation: orders + inventory account for the full input.
    assert sum(water.values()) + leftover_quantity(10_000, result) == pytest.approx(10_000)
    assert sum(result.shares.values()) + result.leftover_share == 1.0


def test_rework_adds_to_original_orders_pro_rata():
    """Rework batch inputs are added to the original batch's orders using
    the original shares."""
    original = compute_shares(
        1000,
        [AllocationLine(order_id=1, fabric_kg=600), AllocationLine(order_id=2, fabric_kg=400)],
    )
    rework = rework_allocation(original)
    extra_water = allocate_quantity(5_000, rework)
    assert extra_water[1] == pytest.approx(3_000)
    assert extra_water[2] == pytest.approx(2_000)


def test_fabric_demand_with_cutting_waste():
    """Style with 20% cutting waste, 0.2 kg net garment weight, 1,000 units
    → fabric demand 250 kg."""
    assert fabric_demand_kg(1000, 0.2, 20) == pytest.approx(250)


def test_data_quality_mix_not_all_measured_with_defaults():
    """An order touched by an outsourced dye batch on default factors shows
    a data-quality mix ≠ 100% measured."""
    mix = data_quality_mix([
        QualityContribution(amount=70, quality=DataQuality.MEASURED),
        QualityContribution(amount=30, quality=DataQuality.DEFAULT_FACTOR),
    ])
    assert mix["measured"] == pytest.approx(70)
    assert mix["default_factor"] == pytest.approx(30)
    assert mix["measured"] < 100


def test_monthly_overhead_spread_by_mass():
    """Monthly kWh 12,000 with 9,000 attributed to batches → 3,000 kWh
    overhead spread by mass across the month's allocations."""
    spread = spread_overhead(
        12_000,
        9_000,
        [MassPoint(key=1, fabric_kg=600), MassPoint(key=2, fabric_kg=400)],
    )
    assert spread[1] == pytest.approx(1_800)
    assert spread[2] == pytest.approx(1_200)
    assert sum(spread.values()) == pytest.approx(3_000)


# --- engine edge cases beyond the verbatim spec list ---


def test_single_order_batch_is_subdivision():
    result = compute_shares(500, [AllocationLine(order_id=7, fabric_kg=500)])
    assert result.shares[7] == 1.0
    assert result.leftover_share == 0.0


def test_units_allocation():
    result = compute_shares(
        1000,
        [
            AllocationLine(order_id=1, fabric_kg=500, garment_units=3000),
            AllocationLine(order_id=2, fabric_kg=500, garment_units=1000),
        ],
        method=AllocationMethod.UNITS,
    )
    assert result.shares[1] == pytest.approx(0.75)
    assert result.shares[2] == pytest.approx(0.25)


def test_economic_allocation_requires_values():
    with pytest.raises(ValueError, match="order_value"):
        compute_shares(
            1000,
            [
                AllocationLine(order_id=1, fabric_kg=500, order_value=100_000),
                AllocationLine(order_id=2, fabric_kg=500),  # missing value
            ],
            method=AllocationMethod.ECONOMIC,
        )


def test_over_allocation_rejected():
    with pytest.raises(ValueError, match="claim"):
        compute_shares(
            1000,
            [AllocationLine(order_id=1, fabric_kg=700), AllocationLine(order_id=2, fabric_kg=400)],
        )


def test_shares_sum_exactly_to_one_awkward_floats():
    """Residual correction: three-way splits with repeating binary fractions
    still sum to exactly 1.0."""
    result = compute_shares(
        999,
        [
            AllocationLine(order_id=1, fabric_kg=333),
            AllocationLine(order_id=2, fabric_kg=333),
            AllocationLine(order_id=3, fabric_kg=333),
        ],
    )
    assert sum(result.shares.values()) + result.leftover_share == 1.0


def test_negative_overhead_clamped():
    spread = spread_overhead(8_000, 9_000, [MassPoint(key=1, fabric_kg=100)])
    assert spread[1] == 0.0
