from typing import Optional

from sqlalchemy.orm import Session

from app.models.patient import Patient


def get_patient_by_id(db: Session, patient_id: int) -> Optional[Patient]:
    return db.query(Patient).filter(Patient.patient_id == patient_id).first()


def create_patient(db: Session, name: str, age: Optional[int], gender: Optional[str]) -> Patient:
    patient = Patient(name=name, age=age, gender=gender)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient
