from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class AdminAuthFields(BaseModel):
    user_id: int = Field(..., description="ID of the authenticated admin")
    email: EmailStr = Field(..., description="Email of the authenticated admin")
    auth_token: str = Field(..., description="Auth token issued at login")


class HospitalCreateRequest(AdminAuthFields):
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    hrr_id: Optional[int] = None
    hrr_city: Optional[str] = None
    total_beds: Optional[int] = None
    total_icu_beds: Optional[int] = None


class HospitalUpdateRequest(AdminAuthFields):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    hrr_id: Optional[int] = None
    hrr_city: Optional[str] = None
    total_beds: Optional[int] = None
    total_icu_beds: Optional[int] = None


class HospitalResponse(BaseModel):
    hospital_id: int
    hospital_pk: Optional[str] = None
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    hrr_id: Optional[int] = None
    hrr_city: Optional[str] = None
    total_beds: Optional[int] = None
    total_icu_beds: Optional[int] = None

    class Config:
        from_attributes = True


class HospitalActionResponse(BaseModel):
    message: str
    hospital: HospitalResponse


class HospitalListResponse(BaseModel):
    count: int
    hospitals: List[HospitalResponse]


class HospitalDeleteResponse(BaseModel):
    message: str
    hospital_id: int


class OccupancyResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    total_beds: Optional[int] = None
    total_icu_beds: Optional[int] = None
    occupied_general: int
    occupied_icu: int
    available_general: Optional[int] = None
    available_icu: Optional[int] = None


class TransferOptionHospital(BaseModel):
    hospital_id: int
    name: str
    city: Optional[str] = None
    is_suggested: bool
    total_beds: Optional[int] = None
    occupied_general: int
    available_general: Optional[int] = None
    total_icu_beds: Optional[int] = None
    occupied_icu: int
    available_icu: Optional[int] = None


class TransferOptionsResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    options: List[TransferOptionHospital]
