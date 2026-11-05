from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.user import (
    create_user,
    delete_user,
    get_user_by_email,
    get_user_by_id,
    list_all_users,
    update_user,
)
from app.models.user import UserRole
from app.schemas.user import (
    AdminAuthFields,
    UserActionResponse,
    UserCreateRequest,
    UserDeleteResponse,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)
from app.services.auth_guard import authenticate_admin

router = APIRouter(prefix="/admin/users", tags=["Admin - User Management"])

VALID_ROLES = {"admin", "staff"}


def _validate_role(role: str) -> UserRole:
    if role not in VALID_ROLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail=f"Role must be one of {sorted(VALID_ROLES)}."
        )
    return UserRole(role)


@router.post("", response_model=UserActionResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(payload: UserCreateRequest, db: Session = Depends(get_db)) -> UserActionResponse:
    authenticate_admin(db, payload.user_id, payload.email, payload.auth_token)

    role = _validate_role(payload.role)
    if role == UserRole.staff and payload.hospital_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="hospital_id is required when creating a staff account."
        )

    try:
        existing = get_user_by_email(db, payload.new_user_email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while checking existing accounts — {format_exception(exc)}",
        ) from exc

    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"An account already exists for '{payload.new_user_email}'."
        )

    try:
        new_user = create_user(db, email=payload.new_user_email, role=role, hospital_id=payload.hospital_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while creating account — {format_exception(exc)}",
        ) from exc

    return UserActionResponse(
        message=f"{role.value.capitalize()} account created for '{new_user.email}'.",
        user=UserResponse.model_validate(new_user),
    )


@router.get("", response_model=UserListResponse)
def list_users_endpoint(
    user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> UserListResponse:
    authenticate_admin(db, user_id, email, auth_token)

    try:
        users = list_all_users(db)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while listing accounts — {format_exception(exc)}",
        ) from exc

    return UserListResponse(count=len(users), users=[UserResponse.model_validate(u) for u in users])


@router.get("/{target_user_id}", response_model=UserResponse)
def get_user_endpoint(
    target_user_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> UserResponse:
    authenticate_admin(db, user_id, email, auth_token)

    target = get_user_by_id(db, target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")

    return UserResponse.model_validate(target)


@router.patch("/{target_user_id}", response_model=UserActionResponse)
def update_user_endpoint(
    target_user_id: int, payload: UserUpdateRequest, db: Session = Depends(get_db)
) -> UserActionResponse:
    authenticate_admin(db, payload.user_id, payload.email, payload.auth_token)

    target = get_user_by_id(db, target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")

    new_role = _validate_role(payload.role) if payload.role is not None else None
    if new_role == UserRole.staff and payload.hospital_id is None and target.hospital_id is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="hospital_id is required when setting role to staff."
        )

    try:
        updated = update_user(db, target, role=new_role, hospital_id=payload.hospital_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while updating account — {format_exception(exc)}",
        ) from exc

    return UserActionResponse(message="Account updated successfully.", user=UserResponse.model_validate(updated))


@router.delete("/{target_user_id}", response_model=UserDeleteResponse)
def delete_user_endpoint(
    target_user_id: int, user_id: int, email: str, auth_token: str, db: Session = Depends(get_db)
) -> UserDeleteResponse:
    admin = authenticate_admin(db, user_id, email, auth_token)

    if target_user_id == admin.user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own account while logged in as it."
        )

    target = get_user_by_id(db, target_user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Account not found.")

    try:
        delete_user(db, target)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete '{target.email}': the database's foreign key constraints haven't been "
                "updated yet. Run scripts/fix_fk_constraints.py once, then try again."
            ),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while deleting account — {format_exception(exc)}",
        ) from exc

    return UserDeleteResponse(message="Account deleted successfully.", user_id=target_user_id)
