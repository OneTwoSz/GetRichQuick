from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Factory
from ..schemas import FactoryCreate, FactoryUpdate, FactoryResponse
from ..utils.auth import get_current_user

router = APIRouter(prefix="/factory", tags=["Factory"])


@router.get("", response_model=FactoryResponse)
async def get_factory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's factory"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found. Please create a factory profile first."
        )

    return factory


@router.post("", response_model=FactoryResponse, status_code=status.HTTP_201_CREATED)
async def create_factory(
    factory_data: FactoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create factory profile"""

    # Check if factory already exists for user
    existing_factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if existing_factory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Factory profile already exists. Use PUT to update."
        )

    # Create new factory
    new_factory = Factory(
        user_id=current_user.id,
        **factory_data.model_dump()
    )

    db.add(new_factory)
    db.commit()
    db.refresh(new_factory)

    return new_factory


@router.put("", response_model=FactoryResponse)
async def update_factory(
    factory_data: FactoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update factory profile"""

    factory = db.query(Factory).filter(Factory.user_id == current_user.id).first()
    if not factory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Factory not found"
        )

    # Update factory
    for key, value in factory_data.model_dump().items():
        setattr(factory, key, value)

    db.commit()
    db.refresh(factory)

    return factory
