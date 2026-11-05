from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.hospital import Hospital, HospitalEdge


def get_hospital_by_id(db: Session, hospital_id: int) -> Optional[Hospital]:
    return db.query(Hospital).filter(Hospital.hospital_id == hospital_id).first()


def list_all_hospitals(db: Session) -> List[Hospital]:
    return db.query(Hospital).order_by(Hospital.hospital_id).all()


def list_hospitals_by_hrr(db: Session, hrr_id: int) -> List[Hospital]:
    return db.query(Hospital).filter(Hospital.hrr_id == hrr_id).order_by(Hospital.hospital_id).all()


def get_neighbor_hospitals(db: Session, hospital_id: int) -> List[Hospital]:
    edges = (
        db.query(HospitalEdge)
        .filter(
            (HospitalEdge.source_hospital_id == hospital_id)
            | (HospitalEdge.target_hospital_id == hospital_id)
        )
        .all()
    )
    neighbor_ids = set()
    for e in edges:
        neighbor_ids.add(
            e.target_hospital_id if e.source_hospital_id == hospital_id else e.source_hospital_id
        )
    if not neighbor_ids:
        return []
    return db.query(Hospital).filter(Hospital.hospital_id.in_(neighbor_ids)).all()


def create_hospital(
    db: Session,
    name: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    hrr_id: Optional[int] = None,
    hrr_city: Optional[str] = None,
    total_beds: Optional[int] = None,
    total_icu_beds: Optional[int] = None,
) -> Hospital:
    hospital = Hospital(
        name=name, city=city, state=state, hrr_id=hrr_id, hrr_city=hrr_city,
        total_beds=total_beds, total_icu_beds=total_icu_beds,
    )
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


def update_hospital(db: Session, hospital: Hospital, **fields) -> Hospital:
    for key, value in fields.items():
        if value is not None:
            setattr(hospital, key, value)
    db.commit()
    db.refresh(hospital)
    return hospital


def delete_hospital(db: Session, hospital: Hospital) -> None:
    db.delete(hospital)
    db.commit()
