"""
Per-SKU product catalog with bills of materials.

This is the schema layer that brings the app from "factory monthly average
carbon" to "this style's per-garment carbon" — the granularity DPP rules
require. Carbon at the product level is computed two ways:

  - **Theoretical**: from the BOM (sum of `qty_per_garment_g/1000 *
    emission_factor`). This is what gets stamped onto a DPP and is
    independent of whether any of this SKU has been produced yet.
  - **Actual**: from `ProductionRecord` rows linked to the product via
    `product_id`. Per-garment is `sum(batch emissions) / sum(garments)`.

The two should converge as the BOM gets refined; divergence is itself a
useful signal.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..models import (
    User,
    Factory,
    Product,
    BillOfMaterialsItem,
    ProductionRecord,
)
from ..schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    BomItemCreate,
    BomItemResponse,
    ProductCarbon,
    ProductCarbonBreakdown,
)
from ..utils.auth import get_current_user
from ..utils.constants import (
    MATERIAL_CARBON_FACTORS,
    MATERIAL_CATEGORY_FALLBACK_FACTORS,
)
from ..services.carbon_calculator import CarbonCalculator

router = APIRouter(prefix="/products", tags=["Products"])


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory before adding products",
        )
    return factory


def _resolve_carbon_factor(item: BillOfMaterialsItem) -> float:
    """Pick the right kg CO2e/kg factor for a BOM line.

    Precedence: explicit override > material_key lookup > category fallback.
    """
    if item.carbon_factor_override is not None:
        return item.carbon_factor_override
    if item.material_key and item.material_key in MATERIAL_CARBON_FACTORS:
        return MATERIAL_CARBON_FACTORS[item.material_key]
    return MATERIAL_CATEGORY_FALLBACK_FACTORS.get(item.category.value, 5.0)


@router.get("", response_model=List[ProductResponse])
def list_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return (
        db.query(Product)
        .filter(Product.factory_id == factory.id)
        .order_by(Product.created_at.desc())
        .all()
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)

    if db.query(Product).filter(
        Product.factory_id == factory.id, Product.sku == payload.sku
    ).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SKU '{payload.sku}' already exists for this factory",
        )

    product = Product(
        factory_id=factory.id,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        fiber_composition=payload.fiber_composition,
        garment_weight_g=payload.garment_weight_g,
        cutting_waste_percent=payload.cutting_waste_percent,
        recycled_content_pct=payload.recycled_content_pct,
        care_instructions=payload.care_instructions,
        target_buyer=payload.target_buyer,
        active=payload.active,
    )
    db.add(product)
    db.flush()  # need product.id for BOM rows

    for bom_item in payload.bom:
        db.add(BillOfMaterialsItem(
            product_id=product.id,
            material_name=bom_item.material_name,
            category=bom_item.category,
            material_key=bom_item.material_key,
            quantity_per_garment_g=bom_item.quantity_per_garment_g,
            carbon_factor_override=bom_item.carbon_factor_override,
            notes=bom_item.notes,
        ))

    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    for field, value in payload.dict().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()


# ---------------------------------------------------------------------------
# BOM line items — managed nested under a product
# ---------------------------------------------------------------------------


@router.post(
    "/{product_id}/bom",
    response_model=BomItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_bom_item(
    product_id: int,
    payload: BomItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    item = BillOfMaterialsItem(
        product_id=product.id,
        **payload.dict(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete(
    "/{product_id}/bom/{bom_item_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_bom_item(
    product_id: int,
    bom_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    item = (
        db.query(BillOfMaterialsItem)
        .join(Product, Product.id == BillOfMaterialsItem.product_id)
        .filter(
            BillOfMaterialsItem.id == bom_item_id,
            BillOfMaterialsItem.product_id == product_id,
            Product.factory_id == factory.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM item not found")
    db.delete(item)
    db.commit()


# ---------------------------------------------------------------------------
# Per-SKU carbon — the headline number for DPP
# ---------------------------------------------------------------------------


@router.get("/{product_id}/carbon", response_model=ProductCarbon)
def product_carbon(
    product_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    breakdown: List[ProductCarbonBreakdown] = []
    total_per_garment_kg = 0.0
    for item in product.bom_items:
        factor = _resolve_carbon_factor(item)
        kg_per_garment = item.quantity_per_garment_g / 1000.0
        emissions = kg_per_garment * factor
        total_per_garment_kg += emissions
        breakdown.append(ProductCarbonBreakdown(
            material_name=item.material_name,
            category=item.category,
            quantity_per_garment_g=item.quantity_per_garment_g,
            carbon_factor=round(factor, 4),
            emissions_per_garment_kg=round(emissions, 4),
        ))

    # Actual observed per-garment carbon — only meaningful if records have
    # been linked to this product via product_id.
    linked = (
        db.query(ProductionRecord)
        .filter(ProductionRecord.product_id == product.id)
        .all()
    )
    actual_per_garment_kg = None
    if linked:
        total_emissions = sum(
            CarbonCalculator.calculate_record_emissions(r)["total"] for r in linked
        )
        total_garments = sum(r.garments_produced for r in linked)
        if total_garments > 0:
            actual_per_garment_kg = round(total_emissions / total_garments, 4)

    return ProductCarbon(
        product_id=product.id,
        sku=product.sku,
        name=product.name,
        total_per_garment_kg=round(total_per_garment_kg, 4),
        breakdown=breakdown,
        actual_per_garment_kg=actual_per_garment_kg,
        batches_observed=len(linked),
    )
