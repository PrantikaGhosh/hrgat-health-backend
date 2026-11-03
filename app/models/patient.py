from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.session import Base


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
