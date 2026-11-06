from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class StaffAuthFields(BaseModel):
    user_id: int = Field(..., description="ID of the authenticated staff/admin user")
    email: EmailStr = Field(..., description="Email of the authenticated staff/admin user")
    auth_token: str = Field(..., description="Auth token issued at login")


class AdmitPatientRequest(StaffAuthFields):
    hospital_id: int
    patient_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    bed_type: str = Field(..., description="'icu' or 'general'")


class DischargeRequest(StaffAuthFields):
    pass


class TransferRequest(StaffAuthFields):
    destination_hospital_id: int
    bed_type: str = Field(..., description="'icu' or 'general', the unit at the destination hospital")


class AdmissionResponse(BaseModel):
    admission_id: int
    patient_id: int
    hospital_id: int
    bed_type: str
    status: str
    admit_time: datetime
    discharge_time: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdmissionActionResponse(BaseModel):
    message: str
    admission: AdmissionResponse
