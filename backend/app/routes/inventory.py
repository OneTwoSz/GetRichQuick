"""
Leftover fabric inventory + chemical stock ledger.

FabricInventory rows are created automatically when a batch completes with
unallocated kg. Consuming a row transfers its embodied footprint to the
consuming order; writing it off books it to the factory waste ledger.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from ..database import get_db
from ..models import (
    Chemical,
    ChemicalStockEntry,
    FabricInventory,
    Factory,
    InventoryStatus,
    Order,
    StockEntryType,
    User,
)
from ..schemas import (
    ChemicalStockBalance,
    ChemicalStockEntryCreate,
    ChemicalStockEntryResponse,
    ConsumeInventoryRequest,
    FabricInventoryResponse,
    WriteOffInventoryRequest,
)
from ..services.audit_logger import AuditLogger
from ..utils.auth import get_current_user

router = APIRouter(prefix="/inventory", tags=["Fabric Inventory"])
stock_router = APIRouter(prefix="/chemical-stock", tags=["Chemical Stock"])


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory first",
        )
    return factory


@router.get("", response_model=List[FabricInventoryResponse])
def list_inventory(
    status_filter: Optional[InventoryStatus] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    query = db.query(FabricInventory).filter(FabricInventory.factory_id == factory.id)
    if status_filter:
        query = query.filter(FabricInventory.status == status_filter)
    return query.order_by(FabricInventory.created_at.desc()).all()


@router.post("/{item_id}/consume", response_model=FabricInventoryResponse)
def consume_inventory(
    item_id: int,
    payload: ConsumeInventoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consume leftover fabric for a new order — the embodied footprint
    transfers to that order (no double counting, nothing vanishes)."""
    factory = _factory_for(current_user, db)
    item = db.query(FabricInventory).filter(
        FabricInventory.id == item_id, FabricInventory.factory_id == factory.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    if item.status != InventoryStatus.IN_STOCK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item is {item.status.value}, only in-stock fabric can be consumed",
        )
    order = db.query(Order).filter(
        Order.id == payload.order_id, Order.factory_id == factory.id
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    old_value = AuditLogger.model_to_dict(item)
    item.status = InventoryStatus.CONSUMED
    item.consumed_by_order_id = order.id
    db.commit()
    db.refresh(item)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="fabric_inventory", entity_id=item.id,
        old_value=old_value, new_value=AuditLogger.model_to_dict(item),
    )
    return item


@router.post("/{item_id}/write-off", response_model=FabricInventoryResponse)
def write_off_inventory(
    item_id: int,
    payload: WriteOffInventoryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Book leftover fabric as SOLD (to the recycling trade) or WASTE —
    the factory-level waste ledger."""
    factory = _factory_for(current_user, db)
    item = db.query(FabricInventory).filter(
        FabricInventory.id == item_id, FabricInventory.factory_id == factory.id
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    if item.status != InventoryStatus.IN_STOCK:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Item is {item.status.value}, only in-stock fabric can be written off",
        )
    if payload.status not in (InventoryStatus.SOLD, InventoryStatus.WASTE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Write-off status must be sold or waste",
        )

    old_value = AuditLogger.model_to_dict(item)
    item.status = payload.status
    db.commit()
    db.refresh(item)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="fabric_inventory", entity_id=item.id,
        old_value=old_value, new_value=AuditLogger.model_to_dict(item),
    )
    return item


# --- chemical stock ledger ----------------------------------------------------


@stock_router.get("/balances", response_model=List[ChemicalStockBalance])
def stock_balances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current balance per chemical: purchases − drawdowns ± reconciliation.
    Compliance status rides along from the chemical master record."""
    factory = _factory_for(current_user, db)
    rows = (
        db.query(
            Chemical.id,
            Chemical.chemical_name,
            Chemical.reach_compliant,
            Chemical.zdhc_compliant,
            func.coalesce(func.sum(ChemicalStockEntry.quantity_kg), 0.0).label("balance"),
        )
        .outerjoin(ChemicalStockEntry, ChemicalStockEntry.chemical_id == Chemical.id)
        .filter(Chemical.factory_id == factory.id)
        .group_by(Chemical.id)
        .all()
    )
    return [
        ChemicalStockBalance(
            chemical_id=r.id,
            chemical_name=r.chemical_name,
            balance_kg=round(r.balance, 3),
            reach_compliant=r.reach_compliant,
            zdhc_compliant=r.zdhc_compliant,
        )
        for r in rows
    ]


@stock_router.get("", response_model=List[ChemicalStockEntryResponse])
def list_stock_entries(
    chemical_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    query = db.query(ChemicalStockEntry).filter(ChemicalStockEntry.factory_id == factory.id)
    if chemical_id:
        query = query.filter(ChemicalStockEntry.chemical_id == chemical_id)
    return query.order_by(ChemicalStockEntry.created_at.desc()).all()


@stock_router.post("", response_model=ChemicalStockEntryResponse,
                   status_code=status.HTTP_201_CREATED)
def create_stock_entry(
    payload: ChemicalStockEntryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manual ledger entries: PURCHASE (positive) and periodic physical
    RECONCILIATION (signed variance). DRAWDOWN rows are created
    automatically by batch inputs — reject them here to keep the trail
    honest."""
    factory = _factory_for(current_user, db)
    if payload.entry_type == StockEntryType.DRAWDOWN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Drawdowns are booked automatically when a batch logs a chemical input",
        )
    if payload.entry_type == StockEntryType.PURCHASE and payload.quantity_kg <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Purchases must have positive quantity",
        )
    chemical = db.query(Chemical).filter(
        Chemical.id == payload.chemical_id, Chemical.factory_id == factory.id
    ).first()
    if not chemical:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chemical_id does not belong to this factory",
        )

    entry = ChemicalStockEntry(factory_id=factory.id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="chemical_stock_entry", entity_id=entry.id,
        new_value=AuditLogger.model_to_dict(entry),
    )
    return entry
