"""
Production batches — the primary data-entry unit of phase 2. "New Batch" is
the main action, not "New Order Report": batch code, process, colour,
fabric kg, then meter readings / chemical drawdowns. Orders attach to a
batch (possibly later — factories often know the lot before the final order
split) and the allocation engine stores each order's share.

Also carries the job-work flow: a batch flagged `outsourced` gets a token
URL the dyeing unit can open without a login to submit actual consumption.
"""


from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..database import get_db
from ..models import (
    BatchAllocation,
    BatchInput,
    BatchInputType,
    Chemical,
    ChemicalStockEntry,
    FabricInventory,
    Factory,
    JobWorker,
    Order,
    ProductionBatch,
    Product,
    StockEntryType,
    User,
)
from ..schemas import (
    AttachOrdersRequest,
    BatchInputCreate,
    BatchInputResponse,
    JobWorkerCreate,
    JobWorkerResponse,
    JobWorkSubmission,
    ProductionBatchCreate,
    ProductionBatchResponse,
    ProductionBatchUpdate,
)
from ..services import batch_carbon
from ..services.allocation import AllocationLine, compute_shares, fabric_demand_kg
from ..services.audit_logger import AuditLogger
from ..config import settings
from ..utils import links
from ..utils.auth import get_current_user
from ..utils.timeutil import as_utc, is_past

router = APIRouter(prefix="/batches", tags=["Production Batches"])
jobworker_router = APIRouter(prefix="/job-workers", tags=["Job Workers"])
# Public, login-free router for outsourced-process data requests.
jobwork_router = APIRouter(prefix="/jobwork", tags=["Job Work (public)"])

_DRAWDOWN_TYPES = {BatchInputType.CHEMICAL_KG, BatchInputType.DYE_KG}


def _factory_for(user: User, db: Session) -> Factory:
    factory = db.query(Factory).filter(Factory.user_id == user.id).first()
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found — set up your factory first",
        )
    return factory


def _get_batch(batch_id: int, factory: Factory, db: Session) -> ProductionBatch:
    batch = db.query(ProductionBatch).filter(
        ProductionBatch.id == batch_id, ProductionBatch.factory_id == factory.id
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


def _add_input(db: Session, batch: ProductionBatch, payload: BatchInputCreate) -> BatchInput:
    """Create a BatchInput; chemical/dye inputs also draw down the stock
    ledger so compliance status flows onto the batch and reconciliation has
    something to check against."""
    if payload.chemical_id is not None:
        chemical = db.query(Chemical).filter(
            Chemical.id == payload.chemical_id,
            Chemical.factory_id == batch.factory_id,
        ).first()
        if not chemical:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="chemical_id does not belong to this factory",
            )
    row = BatchInput(batch_id=batch.id, **payload.model_dump())
    db.add(row)
    db.flush()
    if payload.chemical_id is not None and payload.input_type in _DRAWDOWN_TYPES:
        db.add(ChemicalStockEntry(
            factory_id=batch.factory_id,
            chemical_id=payload.chemical_id,
            entry_type=StockEntryType.DRAWDOWN,
            quantity_kg=-payload.quantity,
            batch_input_id=row.id,
            note=f"drawdown by batch {batch.batch_code}",
        ))
    return row


@router.get("", response_model=List[ProductionBatchResponse])
def list_batches(
    process_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    query = db.query(ProductionBatch).filter(ProductionBatch.factory_id == factory.id)
    if process_type:
        query = query.filter(ProductionBatch.process_type == process_type)
    return query.order_by(ProductionBatch.started_at.desc()).all()


@router.post("", response_model=ProductionBatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: ProductionBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)

    if payload.is_rework:
        if not payload.rework_of_batch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A rework batch must reference the failed original via rework_of_batch_id",
            )
        _get_batch(payload.rework_of_batch_id, factory, db)  # ownership check

    if payload.job_worker_id is not None:
        worker = db.query(JobWorker).filter(
            JobWorker.id == payload.job_worker_id, JobWorker.factory_id == factory.id
        ).first()
        if not worker:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="job_worker_id does not belong to this factory",
            )

    data = payload.model_dump()
    inputs = data.pop("inputs", [])
    batch = ProductionBatch(factory_id=factory.id, created_by=current_user.id, **data)
    db.add(batch)
    db.flush()
    for input_payload in payload.inputs:
        _add_input(db, batch, input_payload)
    db.commit()
    db.refresh(batch)

    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="production_batch", entity_id=batch.id,
        new_value=AuditLogger.model_to_dict(batch),
    )
    return batch


@router.get("/{batch_id}", response_model=ProductionBatchResponse)
def get_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return _get_batch(batch_id, factory, db)


@router.put("/{batch_id}", response_model=ProductionBatchResponse)
def update_batch(
    batch_id: int,
    payload: ProductionBatchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    old_value = AuditLogger.model_to_dict(batch)

    for key, value in payload.model_dump().items():
        setattr(batch, key, value)
    db.commit()
    db.refresh(batch)

    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="production_batch", entity_id=batch.id,
        old_value=old_value, new_value=AuditLogger.model_to_dict(batch),
    )
    return batch


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    if batch.reworks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch has rework runs attached — delete those first",
        )
    old_value = AuditLogger.model_to_dict(batch)
    db.delete(batch)
    db.commit()
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="DELETE", entity_type="production_batch", entity_id=batch_id,
        old_value=old_value,
    )


# --- inputs -----------------------------------------------------------------


@router.post("/{batch_id}/inputs", response_model=BatchInputResponse,
             status_code=status.HTTP_201_CREATED)
def add_batch_input(
    batch_id: int,
    payload: BatchInputCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    row = _add_input(db, batch, payload)
    db.commit()
    db.refresh(row)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="CREATE", entity_type="batch_input", entity_id=row.id,
        new_value=AuditLogger.model_to_dict(row),
    )
    return row


@router.delete("/{batch_id}/inputs/{input_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch_input(
    batch_id: int,
    input_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    row = db.query(BatchInput).filter(
        BatchInput.id == input_id, BatchInput.batch_id == batch.id
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Input not found")
    old_value = AuditLogger.model_to_dict(row)
    # Reverse any stock drawdown this input booked.
    db.query(ChemicalStockEntry).filter(
        ChemicalStockEntry.batch_input_id == row.id
    ).delete()
    db.delete(row)
    db.commit()
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="DELETE", entity_type="batch_input", entity_id=input_id,
        old_value=old_value,
    )


# --- order allocation --------------------------------------------------------


@router.post("/{batch_id}/allocations", response_model=ProductionBatchResponse)
def attach_orders(
    batch_id: int,
    payload: AttachOrdersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach orders to a batch and store the allocation split.

    fabric_kg per line defaults to the order's computed demand
    (units × net weight ÷ (1 − cutting waste%)) so the style that wastes
    more fabric correctly carries more of the batch footprint. Replaces any
    existing allocation set — re-attaching is how factories fix the split
    once the real order mix is known."""
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    if batch.is_rework:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rework batches inherit the original batch's allocation — attach orders there",
        )

    lines: List[AllocationLine] = []
    orders: dict[int, Order] = {}
    for line in payload.lines:
        order = db.query(Order).filter(
            Order.id == line.order_id, Order.factory_id == factory.id
        ).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Order {line.order_id} not found",
            )
        fabric_kg = line.fabric_kg
        if fabric_kg is None:
            product = db.query(Product).filter(Product.id == order.product_id).first()
            fabric_kg = fabric_demand_kg(
                order.units,
                product.garment_weight_g / 1000.0,
                product.cutting_waste_percent or 0,
            )
        orders[order.id] = order
        lines.append(AllocationLine(
            order_id=order.id,
            fabric_kg=fabric_kg,
            garment_units=order.units,
            order_value=order.order_value,
        ))

    try:
        result = compute_shares(batch.total_fabric_kg, lines, batch.allocation_method)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    db.query(BatchAllocation).filter(BatchAllocation.batch_id == batch.id).delete()
    for line in lines:
        order = orders[line.order_id]
        db.add(BatchAllocation(
            batch_id=batch.id,
            order_id=line.order_id,
            product_id=order.product_id,
            fabric_kg=line.fabric_kg,
            garment_units=line.garment_units,
            order_value=line.order_value,
            allocated_share=result.shares[line.order_id],
        ))
    db.commit()
    db.refresh(batch)

    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="batch_allocations", entity_id=batch.id,
        new_value={
            "method": result.method.value,
            "shares": {str(k): v for k, v in result.shares.items()},
            "leftover_share": result.leftover_share,
        },
    )
    return batch


@router.post("/{batch_id}/complete", response_model=ProductionBatchResponse)
def complete_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a batch complete. Unallocated kg flow to FabricInventory with
    their pro-rata embodied CO2 and water (batch + its rework runs), so the
    buffer fabric's footprint neither vanishes nor double-counts."""
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    if batch.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Batch already completed"
        )

    batch.completed_at = datetime.now(timezone.utc)

    result = batch_carbon.stored_allocation_result(batch)
    if result.leftover_fabric_kg > 0:
        totals = batch_carbon.batch_totals(batch)
        co2 = totals.co2_kg
        water = totals.water_l
        for rework in batch.reworks:
            rework_totals = batch_carbon.batch_totals(rework)
            co2 += rework_totals.co2_kg
            water += rework_totals.water_l
        db.add(FabricInventory(
            factory_id=factory.id,
            source_batch_id=batch.id,
            fabric_kg=result.leftover_fabric_kg,
            embodied_co2_kg=round(co2 * result.leftover_share, 4),
            embodied_water_l=round(water * result.leftover_share, 2),
        ))

    db.commit()
    db.refresh(batch)
    AuditLogger.log_action(
        db=db, factory_id=factory.id, user_id=current_user.id,
        action="UPDATE", entity_type="production_batch", entity_id=batch.id,
        new_value={"completed_at": batch.completed_at.isoformat(),
                   "leftover_fabric_kg": result.leftover_fabric_kg},
    )
    return batch


# --- job workers & the login-free request link --------------------------------


@jobworker_router.get("", response_model=List[JobWorkerResponse])
def list_job_workers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    return db.query(JobWorker).filter(JobWorker.factory_id == factory.id).all()


@jobworker_router.post("", response_model=JobWorkerResponse,
                       status_code=status.HTTP_201_CREATED)
def create_job_worker(
    payload: JobWorkerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    factory = _factory_for(current_user, db)
    worker = JobWorker(factory_id=factory.id, **payload.model_dump())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


@router.post("/{batch_id}/jobwork-link", response_model=ProductionBatchResponse)
def create_jobwork_link(
    batch_id: int,
    rotate: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint the token URL a job worker uses to submit actuals — data path 1
    (MEASURED) of the outsourcing spec. Single form, no login.

    Links expire after JOBWORK_LINK_DAYS and accept JOBWORK_MAX_SUBMISSIONS
    submissions; `rotate=true` issues a fresh link (old URL stops working)."""
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    if not batch.outsourced:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job-work links are for batches flagged outsourced",
        )
    if rotate or not batch.job_work_token or is_past(batch.job_work_expires_at):
        batch.job_work_token = links.new_token()
        batch.job_work_expires_at = links.expiry(settings.JOBWORK_LINK_DAYS)
        batch.job_work_submissions = 0
        db.commit()
        db.refresh(batch)
    return batch


@router.delete("/{batch_id}/jobwork-link", response_model=ProductionBatchResponse)
def revoke_jobwork_link(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop the job-work link working immediately."""
    factory = _factory_for(current_user, db)
    batch = _get_batch(batch_id, factory, db)
    batch.job_work_token = None
    batch.job_work_expires_at = None
    db.commit()
    db.refresh(batch)
    return batch


@jobwork_router.get("/{token}")
def jobwork_request_info(token: str, request: Request, db: Session = Depends(get_db)):
    """What the job worker sees when they open the link: just enough
    context to fill the form."""
    links.throttle_lookup(request, "jobwork")
    batch = db.query(ProductionBatch).filter(
        ProductionBatch.job_work_token == token
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    links.ensure_usable(expires_at=batch.job_work_expires_at)
    factory = db.query(Factory).filter(Factory.id == batch.factory_id).first()
    return {
        "batch_code": batch.batch_code,
        "process_type": batch.process_type.value,
        "colour": batch.colour,
        "total_fabric_kg": batch.total_fabric_kg,
        "factory_name": factory.name if factory else None,
        "already_submitted": len(batch.inputs) > 0,
        "expires_at": as_utc(batch.job_work_expires_at),
        "submissions_left": (None if batch.job_work_expires_at is None
                             else max(settings.JOBWORK_MAX_SUBMISSIONS - (batch.job_work_submissions or 0), 0)),
    }


@jobwork_router.post("/{token}", status_code=status.HTTP_201_CREATED)
def jobwork_submit(
    token: str,
    payload: JobWorkSubmission,
    request: Request,
    db: Session = Depends(get_db),
):
    """Job worker posts actual consumption for the outsourced batch."""
    links.throttle_lookup(request, "jobwork")
    batch = db.query(ProductionBatch).filter(
        ProductionBatch.job_work_token == token
    ).first()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    links.ensure_usable(expires_at=batch.job_work_expires_at)
    # Links minted before limits existed (no expiry) keep working unlimited.
    if batch.job_work_expires_at is not None:
        links.ensure_submissions_left(batch.job_work_submissions or 0, settings.JOBWORK_MAX_SUBMISSIONS)
    links.throttle_submit(request, "jobwork")

    created = []
    for input_payload in payload.inputs:
        # Chemical FKs are the factory's inventory; a job worker can't
        # reference them from outside.
        input_payload.chemical_id = None
        source = "job worker submission"
        if payload.submitted_by:
            source += f" ({payload.submitted_by})"
        input_payload.source = source
        row = BatchInput(batch_id=batch.id, **input_payload.model_dump())
        db.add(row)
        created.append(row)
    batch.job_work_submissions = (batch.job_work_submissions or 0) + 1
    db.commit()

    AuditLogger.log_action(
        db=db, factory_id=batch.factory_id, user_id=batch.created_by,
        action="CREATE", entity_type="jobwork_submission", entity_id=batch.id,
        new_value={"inputs": len(created), "submitted_by": payload.submitted_by},
    )
    return {"status": "ok", "inputs_recorded": len(created)}
