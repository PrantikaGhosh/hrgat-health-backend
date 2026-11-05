from typing import List
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.admission import count_occupied_beds, get_active_admissions_for_hospital, get_occupancy_summary_for_all_hospitals
from app.crud.hospital import get_hospital_by_id, get_neighbor_hospitals, list_all_hospitals, list_hospitals_by_hrr
from app.crud.patient import get_patient_by_id
from app.schemas.forecast import ForecastResponse, HistoryPoint, HistoryResponse
from app.schemas.hospital import (
    HospitalListResponse,
    HospitalResponse,
    OccupancyResponse,
    TransferOptionHospital,
    TransferOptionsResponse,
)
from app.schemas.patient import HospitalPatientResponse
from app.services.auth_guard import authenticate_staff_or_admin, authenticate_user
from app.services.forecast_service import (
    BEDS_TARGET_COL,
    ICU_TARGET_COL,
    get_forecast_for_hospital_live,
    get_history_for_hospital,
    get_latest_raw_value,
    shift_week_label,
)

router = APIRouter(prefix="/hospitals", tags=["Hospitals"])
hrr_router = APIRouter(prefix="/hrr", tags=["Hospitals"])


def _validate_target(target: str) -> None:
    if target not in ("icu", "beds"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="target must be 'icu' or 'beds'.")


@router.get("", response_model=HospitalListResponse)
def list_hospitals(user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)) -> HospitalListResponse:
    authenticate_user(db, user_id, email, auth_token)
    try:
        hospitals = list_all_hospitals(db)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while listing hospitals — {format_exception(exc)}",
        ) from exc
    return HospitalListResponse(count=len(hospitals), hospitals=[HospitalResponse.model_validate(h) for h in hospitals])


@router.get("/{hospital_id}", response_model=HospitalResponse)
def get_hospital(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> HospitalResponse:
    authenticate_user(db, user_id, email, auth_token)
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    return HospitalResponse.model_validate(hospital)


@router.get("/{hospital_id}/neighbors", response_model=HospitalListResponse)
def get_hospital_neighbors(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> HospitalListResponse:
    authenticate_user(db, user_id, email, auth_token)
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    try:
        neighbors = get_neighbor_hospitals(db, hospital_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching neighbors — {format_exception(exc)}",
        ) from exc
    return HospitalListResponse(count=len(neighbors), hospitals=[HospitalResponse.model_validate(h) for h in neighbors])


@router.get("/{hospital_id}/transfer-options", response_model=TransferOptionsResponse)
def get_transfer_options(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> TransferOptionsResponse:
    """
    Hospitals worth considering for a transfer out of this one.
    Referral-network neighbors are marked is_suggested and sorted
    first, since those are the structurally connected hospitals your
    STGAT model actually reasons about. Every hospital is annotated
    with live per-unit availability computed from real admissions,
    and hospitals with zero room in BOTH units are excluded entirely,
    there's no point suggesting a transfer destination that's full.
    An unknown capacity (None) is treated as available, since we
    can't judge a limit we don't know.
    """
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    try:
        neighbor_ids = {n.hospital_id for n in get_neighbor_hospitals(db, hospital_id)}
        all_hospitals = [h for h in list_all_hospitals(db) if h.hospital_id != hospital_id]
        occupancy_summary = get_occupancy_summary_for_all_hospitals(db)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while building transfer options — {format_exception(exc)}",
        ) from exc

    options = []
    for h in all_hospitals:
        counts = occupancy_summary.get(h.hospital_id, {"icu": 0, "general": 0})
        occupied_icu = counts["icu"]
        occupied_general = counts["general"]
        available_icu = (h.total_icu_beds - occupied_icu) if h.total_icu_beds is not None else None
        available_general = (h.total_beds - occupied_general) if h.total_beds is not None else None

        icu_has_room = available_icu is None or available_icu > 0
        general_has_room = available_general is None or available_general > 0
        if not icu_has_room and not general_has_room:
            continue

        options.append(
            TransferOptionHospital(
                hospital_id=h.hospital_id,
                name=h.name,
                city=h.city,
                is_suggested=h.hospital_id in neighbor_ids,
                total_beds=h.total_beds,
                occupied_general=occupied_general,
                available_general=available_general,
                total_icu_beds=h.total_icu_beds,
                occupied_icu=occupied_icu,
                available_icu=available_icu,
            )
        )

    options.sort(key=lambda o: (not o.is_suggested, o.name))

    return TransferOptionsResponse(hospital_id=hospital.hospital_id, hospital_name=hospital.name, options=options)


@router.get("/{hospital_id}/occupancy", response_model=OccupancyResponse)
def get_occupancy(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> OccupancyResponse:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    try:
        counts = count_occupied_beds(db, hospital_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while computing occupancy — {format_exception(exc)}",
        ) from exc

    available_general = (hospital.total_beds - counts["general"]) if hospital.total_beds is not None else None
    available_icu = (hospital.total_icu_beds - counts["icu"]) if hospital.total_icu_beds is not None else None

    return OccupancyResponse(
        hospital_id=hospital.hospital_id,
        hospital_name=hospital.name,
        total_beds=hospital.total_beds,
        total_icu_beds=hospital.total_icu_beds,
        occupied_general=counts["general"],
        occupied_icu=counts["icu"],
        available_general=available_general,
        available_icu=available_icu,
    )


@router.get("/{hospital_id}/patients", response_model=List[HospitalPatientResponse])
def get_hospital_patients(
    hospital_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> List[HospitalPatientResponse]:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")

    try:
        active_admissions = get_active_admissions_for_hospital(db, hospital_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while fetching patients — {format_exception(exc)}",
        ) from exc

    results = []
    for adm in active_admissions:
        p = get_patient_by_id(db, adm.patient_id)
        if p is not None:
            results.append(
                HospitalPatientResponse(
                    admission_id=adm.admission_id,
                    patient_id=p.patient_id,
                    name=p.name,
                    age=p.age,
                    gender=p.gender,
                    bed_type=adm.bed_type.value,
                    admit_time=adm.admit_time,
                )
            )
    return results


@router.get("/{hospital_id}/forecast", response_model=ForecastResponse)
def get_hospital_forecast(
    hospital_id: int,
    user_id: int,
    email: str,
    auth_token: str,
    target: str = "icu",
    db: Session = Depends(get_db),
) -> ForecastResponse:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    _validate_target(target)

    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    if hospital.hospital_pk is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="This hospital was not part of the trained model, no forecast available.",
        )

    try:
        counts = count_occupied_beds(db, hospital_id)
        live_addition = counts["icu"] if target == "icu" else counts["general"]
        predicted_value, last_week, _ = get_forecast_for_hospital_live(hospital.hospital_pk, target, live_addition)
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Model or data file missing — {format_exception(exc)}"
        ) from exc

    if predicted_value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No forecast available for this hospital.")

    return ForecastResponse(
        hospital_id=hospital.hospital_id,
        hospital_name=hospital.name,
        target=target,
        predicted_value=round(predicted_value, 2),
        based_on_week=shift_week_label(last_week),
        predicted_week=shift_week_label(last_week + timedelta(weeks=1)),
    )


@router.get("/{hospital_id}/history", response_model=HistoryResponse)
def get_hospital_history(
    hospital_id: int,
    user_id: int,
    email: str,
    auth_token: str,
    target: str = "icu",
    weeks: int = 26,
    db: Session = Depends(get_db),
) -> HistoryResponse:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    _validate_target(target)

    hospital = get_hospital_by_id(db, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hospital not found.")
    if hospital.hospital_pk is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This hospital has no historical data on file.")

    target_col = ICU_TARGET_COL if target == "icu" else BEDS_TARGET_COL
    series = get_history_for_hospital(hospital.hospital_pk, target_col, weeks)

    points = [
        HistoryPoint(week=shift_week_label(row.collection_week), value=round(float(row[target_col]), 2))
        for _, row in series.iterrows()
    ]

    # Append a live "this week" point: last known real value plus net
    # admissions/discharges/transfers recorded in this demo since
    # seeding, so the chart reflects real actions instead of stopping
    # at frozen 2024 data. See forecast_service.py for the full
    # reasoning behind this approximation.
    counts = count_occupied_beds(db, hospital_id)
    live_addition = counts["icu"] if target == "icu" else counts["general"]
    baseline = get_latest_raw_value(hospital.hospital_pk, target_col)
    if baseline is not None:
        points.append(HistoryPoint(week="This week", value=round(baseline + live_addition, 2)))

    return HistoryResponse(hospital_id=hospital.hospital_id, hospital_name=hospital.name, target=target, history=points)


@hrr_router.get("/{hrr_id}/hospitals", response_model=HospitalListResponse)
def get_hospitals_by_hrr(
    hrr_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> HospitalListResponse:
    authenticate_user(db, user_id, email, auth_token)
    try:
        hospitals = list_hospitals_by_hrr(db, hrr_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error — {format_exception(exc)}"
        ) from exc
    return HospitalListResponse(count=len(hospitals), hospitals=[HospitalResponse.model_validate(h) for h in hospitals])
