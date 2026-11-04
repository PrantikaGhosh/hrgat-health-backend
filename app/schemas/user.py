from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class AdminAuthFields(BaseModel):
    """Every admin-only action carries these three fields, matching the
    same auth pattern used throughout the API (no bearer headers, the
    caller's identity is verified explicitly on every request)."""
    user_id: int = Field(..., description="ID of the authenticated admin")
    email: EmailStr = Field(..., description="Email of the authenticated admin")
    auth_token: str = Field(..., description="Auth token issued at login")


class UserCreateRequest(AdminAuthFields):
    new_user_email: EmailStr = Field(..., description="Email of the account to create")
    role: str = Field(..., description="'admin' or 'staff'")
    hospital_id: Optional[int] = Field(
        None, description="Required if role is 'staff', the hospital they work at"
    )


class UserUpdateRequest(AdminAuthFields):
    role: Optional[str] = Field(None, description="New role, if changing it")
    hospital_id: Optional[int] = Field(None, description="New hospital assignment, if changing it")


class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    role: str
    hospital_id: Optional[int] = None

    class Config:
        from_attributes = True


class UserActionResponse(BaseModel):
    message: str
    user: UserResponse


class UserListResponse(BaseModel):
    count: int
    users: List[UserResponse]


class UserDeleteResponse(BaseModel):
    message: str
    user_id: int
