from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import User, Factory, Chemical
from ..schemas import ChemicalCreate, ChemicalUpdate, ChemicalResponse
from ..utils.auth import get_current_user
from ..services.audit_logger import AuditLogger
from ..utils.constants import RESTRICTED_CAS_NUMBERS

router = APIRouter(prefix="/chemicals", tags=["Chemicals"])


@router.get("", response_model=List[ChemicalResponse])
async def get_chemicals(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all chemicals for current factory"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    chemicals = db.query(Chemical).filter(Chemical.factory_id == factory.id).all()
    return chemicals


@router.post("", response_model=ChemicalResponse, status_code=status.HTTP_201_CREATED)
async def create_chemical(
    chemical_data: ChemicalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chemical entry"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Create new chemical
    new_chemical = Chemical(
        factory_id=factory.id,
        **chemical_data.model_dump()
    )

    db.add(new_chemical)
    db.commit()
    db.refresh(new_chemical)

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="CREATE",
        entity_type="chemical",
        entity_id=new_chemical.id,
        new_value=AuditLogger.model_to_dict(new_chemical)
    )

    return new_chemical


@router.put("/{chemical_id}", response_model=ChemicalResponse)
async def update_chemical(
    chemical_id: int,
    chemical_data: ChemicalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a chemical entry"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    chemical = db.query(Chemical).filter(
        Chemical.id == chemical_id,
        Chemical.factory_id == factory.id
    ).first()

    if not chemical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chemical not found"
        )

    # Store old values for audit
    old_value = AuditLogger.model_to_dict(chemical)

    # Update chemical
    for key, value in chemical_data.model_dump().items():
        setattr(chemical, key, value)

    db.commit()
    db.refresh(chemical)

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="UPDATE",
        entity_type="chemical",
        entity_id=chemical.id,
        old_value=old_value,
        new_value=AuditLogger.model_to_dict(chemical)
    )

    return chemical


@router.delete("/{chemical_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chemical(
    chemical_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a chemical entry"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    chemical = db.query(Chemical).filter(
        Chemical.id == chemical_id,
        Chemical.factory_id == factory.id
    ).first()

    if not chemical:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chemical not found"
        )

    # Store old values for audit
    old_value = AuditLogger.model_to_dict(chemical)

    # Delete chemical
    db.delete(chemical)
    db.commit()

    # Log to audit trail
    AuditLogger.log_action(
        db=db,
        factory_id=factory.id,
        user_id=current_user.id,
        action="DELETE",
        entity_type="chemical",
        entity_id=chemical_id,
        old_value=old_value
    )


@router.get("/compliance-check/{cas_number}")
async def check_chemical_compliance(
    cas_number: str,
    current_user: User = Depends(get_current_user)
):
    """Check if a chemical CAS number is on the restricted list"""

    is_restricted = cas_number in RESTRICTED_CAS_NUMBERS

    return {
        "cas_number": cas_number,
        "is_restricted": is_restricted,
        "recommendation": "Do not use - restricted substance" if is_restricted else "Chemical not on restricted list"
    }
