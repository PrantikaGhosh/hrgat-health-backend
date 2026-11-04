from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address to send the login OTP to")


class LoginResponse(BaseModel):
    message: str
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr = Field(..., description="Email address the OTP was sent to")
    otp: int = Field(..., ge=1000, le=9999, description="4-digit OTP received via email")


class VerifyOtpResponse(BaseModel):
    message: str
    user_id: int
    email: EmailStr
    role: str
    hospital_id: Optional[int] = None
    auth_token: str
    auth_token_exp_time: datetime
