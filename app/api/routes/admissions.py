from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.admission import (
    count_occupied_beds,
    create_admission,
    discharge_admission,
    get_admission_by_id,
    mark_transferred,
)
from app.crud.hospital import get_hospital_by_id
from app.crud.patient import create_patient
from app.models.admission import AdmissionStatus, BedType
from app.models.hospital import Hospital
from app.schemas.admission import (
    AdmissionActionResponse,
    AdmissionResponse,
    AdmitPatientRequest,
    DischargeRequest,
    TransferRequest,
)
from app.services.auth_guard import authenticate_staff_for_hospital, authenticate_staff_or_admin, check_staff_hospital_match

router = APIRouter(prefix="/admissions", tags=["Admissions"])


def _validate_bed_type(bed_type: str) -> BedType:
    if bed_type not in ("icu", "general"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="bed_type must be 'icu' or 'general'.")
    return BedType(bed_type)


def _check_capacity(db, hospital: Hospital, bed_type: BedType) -> None:
    """
    Blocks admitting/transferring into a bed type the hospital has no
    room for. A capacity of None means "unknown", not "zero", so it's
    never blocked, we simply can't judge an unknown limit. A capacity
    of 0 or a limit already met/exceeded IS blocked, and the error
    points toward the referral network, since that's the actual answer
    when a hospital is full: check a connected hospital instead.
    """
    capacity = hospital.total_icu_beds if bed_type == BedType.icu else hospital.total_beds
    if capacity is None:
        return

    counts = count_occupied_beds(db, hospital.hospital_id)
    current = counts["icu"] if bed_type == BedType.icu else counts["general"]

    if current >= capacity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"No available {bed_type.value} capacity at '{hospital.name}' "
                f"({current}/{capacity} occupied). Check the referral network for a connected hospital with capacity."
            ),
        )


@router.post("", response_model=AdmissionActionResponse, status_code=status.HTTP_201_CREATED)
def admit_patient(payload: AdmitPatientRequest, db: Session = Depends(get_db)) -> AdmissionActionResponse:
    staff = authenticate_staff_for_hospital(db, payload.user_id, payload.email, payload.auth_token, payload.hospital_id)

    hospital = get_hospital_by_id(db, payload.hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    bed_type = _validate_bed_type(payload.bed_type)
    _check_capacity(db, hospital, bed_type)

    try:
        patient = create_patient(db, name=payload.patient_name, age=payload.age, gender=payload.gender)
        admission = create_admission(
            db,
            patient_id=patient.patient_id,
            hospital_id=payload.hospital_id,
            bed_type=bed_type,
            admitted_by_user_id=staff.user_id,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while admitting patient — {format_exception(exc)}",
        ) from exc

    return AdmissionActionResponse(
        message=f"Patient admitted to '{hospital.name}'.", admission=AdmissionResponse.model_validate(admission)
    )


@router.post("/{admission_id}/discharge", response_model=AdmissionActionResponse)
def discharge_patient(
    admission_id: int, payload: DischargeRequest, db: Session = Depends(get_db)
) -> AdmissionActionResponse:
    staff = authenticate_staff_or_admin(db, payload.user_id, payload.email, payload.auth_token)

    admission = get_admission_by_id(db, admission_id)
    if admission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Admission not found.")

    check_staff_hospital_match(staff, admission.hospital_id)

    if admission.status != AdmissionStatus.admitted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Admission is already '{admission.status.value}', cannot discharge."
        )

    try:
        updated = discharge_admission(db, admission)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while discharging patient — {format_exception(exc)}",
        ) from exc

    return AdmissionActionResponse(message="Patient discharged successfully.", admission=AdmissionResponse.model_validate(updated))


@router.post("/{admission_id}/transfer", response_model=AdmissionActionResponse)
def transfer_patient(
    admission_id: int, payload: TransferRequest, db: Session = Depends(get_db)
) -> AdmissionActionResponse:
    staff = authenticate_staff_or_admin(db, payload.user_id, payload.email, payload.auth_token)

    admission = get_admission_by_id(db, admission_id)
    if admission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Admission not found.")

    # Staff can only move patients OUT of their own hospital, the
    # destination is deliberately unrestricted, that's the entire
    # point of a transfer, sending a patient somewhere else.
    check_staff_hospital_match(staff, admission.hospital_id)

    if admission.status != AdmissionStatus.admitted:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Admission is already '{admission.status.value}', cannot transfer."
        )

    destination = get_hospital_by_id(db, payload.destination_hospital_id)
    if destination is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Destination hospital not found.")
    if destination.hospital_id == admission.hospital_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Destination hospital must differ from the current one.")

    destination_bed_type = _validate_bed_type(payload.bed_type)
    _check_capacity(db, destination, destination_bed_type)

    try:
        mark_transferred(db, admission)
        new_admission = create_admission(
            db,
            patient_id=admission.patient_id,
            hospital_id=payload.destination_hospital_id,
            bed_type=destination_bed_type,
            admitted_by_user_id=staff.user_id,
            transferred_from_admission_id=admission.admission_id,
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while transferring patient — {format_exception(exc)}",
        ) from exc

    return AdmissionActionResponse(
        message=f"Patient transferred to '{destination.name}' ({destination_bed_type.value} unit).",
        admission=AdmissionResponse.model_validate(new_admission),
    )
