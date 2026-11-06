from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.crud.patient import get_patient_by_id
from app.schemas.patient import PatientResponse
from app.services.auth_guard import authenticate_staff_or_admin

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> PatientResponse:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    patient = get_patient_by_id(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Patient not found.")
    return PatientResponse.model_validate(patient)
