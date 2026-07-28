"""
Orders — the unit the footprint is reported against (never the unit data is
entered at; that's the batch). Includes the per-order footprint endpoint
(Allocation Statement + data-quality mix) and the buyer-facing read-only
share link, so a factory can answer any brand portal request in one click.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import Factory, Order, OrderStatus, Product, User
from ..schemas import (
    BatchLineOut,
    OrderCreate,
    OrderFootprintResponse,
    OrderResponse,
    OrderUpdate,
)
from ..services import batch_carbon
from ..services.allocation import fabric_demand_kg
from ..services.audit_logger import AuditLogger
from ..utils.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["Orders"])
# Public, login-free router for the buyer share link.
share_router = APIRouter(prefix="/share", tags=["Buyer share link"])


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory first",
        )
    return factory


def _get_order(order_id: int, factory: Factory, db: Session) -> Order:
    order = db.query(Order).filter(
        Order.id == order_id, Order.factory_id == factory.id
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _order_response(order: Order, db: Session) -> OrderResponse:
    resp = OrderResponse.model_validate(order)
    product = db.query(Product).filter(Product.id == order.product_id).first()
    if product:
        resp.fabric_demand_kg = round(fabric_demand_kg(
            order.units, product.garment_weight_g / 1000.0, product.cutting_waste_percent or 0
        ), 2)
    return resp


def build_footprint_response(db: Session, order: Order) -> OrderFootprintResponse:
    """Shared by the authed footprint endpoint and the public share link."""
    fp = batch_carbon.order_footprint(db, order)
    product = db.query(Product).filter(Product.id == order.product_id).first()
    return OrderFootprintResponse(
        order_id=order.id,
        order_code=order.order_code,
        buyer_name=order.buyer_name,
        product_sku=product.sku if product else None,
        product_name=product.name if product else None,
        units=order.units,
        co2_kg=fp.co2_kg,
        co2_per_garment_kg=round(fp.co2_kg / order.units, 4) if order.units else 0,
        water_l=fp.water_l,
        water_per_garment_l=round(fp.water_l / order.units, 2) if order.units else 0,
        batch_lines=[BatchLineOut(**vars(line)) for line in fp.batch_lines],
        embodied_co2_kg=fp.embodied_co2_kg,
        embodied_water_l=fp.embodied_water_l,
        overhead_co2_kg=fp.overhead_co2_kg,
        overhead_water_l=fp.overhead_water_l,
        quality_mix=fp.quality_mix,
        used_economic_allocation=fp.used_economic_allocation,
    )


@router.get("", response_model=List[OrderResponse])
def list_orders(
    status_filter: Optional[OrderStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    query = db.query(Order).filter(Order.factory_id == factory.id)
    if status_filter:
        query = query.filter(Order.status == status_filter)
    return [_order_response(o, db) for o in query.order_by(Order.created_at.desc()).all()]


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    product = db.query(Product).filter(
        Product.id == payload.product_id, Product.factory_id == factory.id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="product_id does not belong to this factory",
        )

    order = Order(
        factory_id=factory.id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="order", entity_id=order.id,
        new_value=AuditLogger.model_to_dict(order),
    )
    return _order_response(order, db)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return _order_response(_get_order(order_id, factory, db), db)


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: OrderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    order = _get_order(order_id, factory, db)
    old_value = AuditLogger.model_to_dict(order)

    for key, value in payload.model_dump().items():
        setattr(order, key, value)
    db.commit()
    db.refresh(order)

    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="order", entity_id=order.id,
        old_value=old_value, new_value=AuditLogger.model_to_dict(order),
    )
    return _order_response(order, db)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    order = _get_order(order_id, factory, db)
    if order.allocations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has batch allocations — detach it from its batches first",
        )
    old_value = AuditLogger.model_to_dict(order)
    db.delete(order)
    db.commit()
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="DELETE", entity_type="order", entity_id=order_id,
        old_value=old_value,
    )


@router.get("/{order_id}/footprint", response_model=OrderFootprintResponse)
def order_footprint(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bottom-up footprint from batch allocations: totals, per-batch
    Allocation Statement, embodied stock transfers, overhead slice, and the
    MEASURED/ESTIMATED/DEFAULT_FACTOR mix auditors ask for."""
    factory = _factory_for(current_user, db)
    return build_footprint_response(db, _get_order(order_id, factory, db))


@router.post("/{order_id}/share-link", response_model=OrderResponse)
def create_share_link(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint (or return) the read-only buyer share token for this order."""
    factory = _factory_for(current_user, db)
    order = _get_order(order_id, factory, db)
    if not order.share_token:
        order.share_token = secrets.token_urlsafe(16)
        db.commit()
        db.refresh(order)
        AuditLogger.log_action(
            db=db, factory_id=factory.id, user_id=current_user.id,
            action="CREATE", entity_type="order_share_link", entity_id=order.id,
            new_value={"share_token": order.share_token},
        )
    return _order_response(order, db)


@share_router.get("/{token}", response_model=OrderFootprintResponse)
def public_share_view(token: str, db: Session = Depends(get_db)):
    """Login-free buyer view: footprint + allocation statement + data
    quality mix. Read-only by construction — nothing here mutates."""
    order = db.query(Order).filter(Order.share_token == token).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Share link not found")
    return build_footprint_response(db, order)
