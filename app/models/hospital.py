from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.session import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id = Column(Integer, primary_key=True, autoincrement=True)
    # Original ML dataset ID (e.g. "450034"), links this row to the
    # trained STGAT model's hospital ordering. Null for hospitals added
    # manually through the admin API, those have no forecast available
    # since they weren't part of model training.
    hospital_pk = Column(String(20), unique=True, nullable=True)
    name = Column(String(150), nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    hrr_id = Column(Integer, nullable=True)
    hrr_city = Column(String(100), nullable=True)
    total_beds = Column(Integer, nullable=True)
    total_icu_beds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HospitalEdge(Base):
    """Referral-network connection between two hospitals (same HRR)."""
    __tablename__ = "hospital_edges"

    edge_id = Column(Integer, primary_key=True, autoincrement=True)
    source_hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id", ondelete="CASCADE"), nullable=False)
    target_hospital_id = Column(Integer, ForeignKey("hospitals.hospital_id", ondelete="CASCADE"), nullable=False)
