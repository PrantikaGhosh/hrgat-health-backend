import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.sql import func

from app.db.session import Base


class BedType(str, enum.Enum):
    icu = "icu"
    general = "general"


class AdmissionStatus(str, enum.Enum):
    admitted = "admitted"
    discharged = "discharged"
    transferred = "transferred"


class Admission(Base):
    __tablename__ = "admissions"

    admission_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.patient_id"), nullable=False)
    hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id"), nullable=False)
    bed_type = Column(Enum(BedType), nullable=False)
    status = Column(Enum(AdmissionStatus), nullable=False, default=AdmissionStatus.admitted)
    admit_time = Column(DateTime(timezone=True), server_default=func.now())
    discharge_time = Column(DateTime(timezone=True), nullable=True)
    admitted_by_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    # If this admission resulted from a transfer, points back to the
    # admission record it was transferred FROM (at the source hospital).
    transferred_from_admission_id = Column(Integer, ForeignKey("admissions.admission_id"), nullable=True)
