from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PatientResponse(BaseModel):
    patient_id: int
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HospitalPatientResponse(BaseModel):
    """
    Used by GET /hospitals/{id}/patients. Includes admission_id and
    bed_type on top of the base patient fields, the frontend needs
    admission_id to call discharge/transfer for a specific patient.
    """
    admission_id: int
    patient_id: int
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    bed_type: str
    admit_time: datetime
