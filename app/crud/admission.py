from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.admission import Admission, AdmissionStatus, BedType


def get_admission_by_id(db: Session, admission_id: int) -> Optional[Admission]:
    return db.query(Admission).filter(Admission.admission_id == admission_id).first()


def get_active_admissions_for_hospital(db: Session, hospital_id: int) -> List[Admission]:
    return (
        db.query(Admission)
        .filter(Admission.hospital_id == hospital_id, Admission.status == AdmissionStatus.admitted)
        .all()
    )


def count_occupied_beds(db: Session, hospital_id: int) -> dict:
    active = get_active_admissions_for_hospital(db, hospital_id)
    return {
        "icu": sum(1 for a in active if a.bed_type == BedType.icu),
        "general": sum(1 for a in active if a.bed_type == BedType.general),
    }


def get_occupancy_summary_for_all_hospitals(db: Session) -> dict:
    """
    One grouped query covering every hospital at once, instead of one
    query per hospital, needed for annotating the full transfer-options
    list with live capacity without N+1 queries. Returns
    {hospital_id: {"icu": count, "general": count}}.
    """
    rows = (
        db.query(Admission.hospital_id, Admission.bed_type, func.count(Admission.admission_id))
        .filter(Admission.status == AdmissionStatus.admitted)
        .group_by(Admission.hospital_id, Admission.bed_type)
        .all()
    )
    summary: dict = {}
    for hospital_id, bed_type, count in rows:
        summary.setdefault(hospital_id, {"icu": 0, "general": 0})
        summary[hospital_id][bed_type.value] = count
    return summary


def create_admission(
    db: Session,
    patient_id: int,
    hospital_id: int,
    bed_type: BedType,
    admitted_by_user_id: int,
    transferred_from_admission_id: Optional[int] = None,
) -> Admission:
    admission = Admission(
        patient_id=patient_id,
        hospital_id=hospital_id,
        bed_type=bed_type,
        status=AdmissionStatus.admitted,
        admitted_by_user_id=admitted_by_user_id,
        transferred_from_admission_id=transferred_from_admission_id,
    )
    db.add(admission)
    db.commit()
    db.refresh(admission)
    return admission


def discharge_admission(db: Session, admission: Admission) -> Admission:
    admission.status = AdmissionStatus.discharged
    admission.discharge_time = func.now()
    db.commit()
    db.refresh(admission)
    return admission


def mark_transferred(db: Session, admission: Admission) -> Admission:
    admission.status = AdmissionStatus.transferred
    admission.discharge_time = func.now()
    db.commit()
    db.refresh(admission)
    return admission
