from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.hospital import create_hospital, delete_hospital, get_hospital_by_id, update_hospital
from app.schemas.hospital import (
    HospitalActionResponse,
    HospitalCreateRequest,
    HospitalDeleteResponse,
    HospitalResponse,
    HospitalUpdateRequest,
)
from app.services.auth_guard import authenticate_admin

router = APIRouter(prefix="/admin/hospitals", tags=["Admin - Hospital Management"])


@router.post("", response_model=HospitalActionResponse, status_code=status.HTTP_201_CREATED)
def create_hospital_endpoint(payload: HospitalCreateRequest, db: Session = Depends(get_db)) -> HospitalActionResponse:
    authenticate_admin(db, payload.user_id, payload.email, payload.auth_token)

    try:
        hospital = create_hospital(
            db,
            name=payload.name,
            city=payload.city,
            state=payload.state,
            hrr_id=payload.hrr_id,
            hrr_city=payload.hrr_city,
            total_beds=payload.total_beds,
            total_icu_beds=payload.total_icu_beds,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating hospital — {format_exception(exc)}",
        ) from exc

    return HospitalActionResponse(
        message=f"Hospital '{hospital.name}' created. Note: manually added hospitals have no "
        "forecast available since they weren't part of the trained model.",
        hospital=HospitalResponse.model_validate(hospital),
    )


@router.patch("/{hospital_id}", response_model=HospitalActionResponse)
def update_hospital_endpoint(
    hospital_id: int, payload: HospitalUpdateRequest, db: Session = Depends(get_db)
) -> HospitalActionResponse:
    authenticate_admin(db, payload.user_id, payload.email, payload.auth_token)

    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    try:
        updated = update_hospital(
            db,
            hospital,
            name=payload.name,
            city=payload.city,
            state=payload.state,
            hrr_id=payload.hrr_id,
            hrr_city=payload.hrr_city,
            total_beds=payload.total_beds,
            total_icu_beds=payload.total_icu_beds,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while updating hospital — {format_exception(exc)}",
        ) from exc

    return HospitalActionResponse(message="Hospital updated successfully.", hospital=HospitalResponse.model_validate(updated))


@router.delete("/{hospital_id}", response_model=HospitalDeleteResponse)
def delete_hospital_endpoint(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> HospitalDeleteResponse:
    authenticate_admin(db, user_id, email, auth_token)

    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    try:
        delete_hospital(db, hospital)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete '{hospital.name}': it has patient admission records on file. "
                "This is a deliberate safeguard against silently erasing patient history."
            ),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while deleting hospital — {format_exception(exc)}",
        ) from exc

    return HospitalDeleteResponse(message="Hospital deleted successfully.", hospital_id=hospital_id)
