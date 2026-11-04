from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.utils import format_exception
from app.crud.user import get_user_by_email, get_user_by_id
from app.models.user import User, UserRole


def authenticate_user(db: Session, user_id: int, email: str, auth_token: str) -> User:
    """Validate user_id, email, and auth_token together before allowing any
    protected operation. Checked in order: user_id exists -> email exists ->
    email belongs to this user_id -> auth_token matches -> auth_token not
    expired (expiry compared using the MySQL server's own clock)."""
    try:
        user_by_id = get_user_by_id(db, user_id)
        if user_by_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User ID not found.")

        user_by_email = get_user_by_email(db, email)
        if user_by_email is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Email not found.")

        if user_by_email.user_id != user_by_id.user_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Email does not belong to this user ID."
            )

        if not user_by_id.auth_token or user_by_id.auth_token != auth_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token.")

        row = (
            db.execute(
                text(
                    "SELECT auth_token_exp_time >= NOW() AS is_valid "
                    "FROM users WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            )
            .mappings()
            .first()
        )
        if not row or not row["is_valid"]:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Auth token has expired. Please login again.",
            )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while authenticating user — {format_exception(exc)}",
        ) from exc

    return user_by_id


def authenticate_admin(db: Session, user_id: int, email: str, auth_token: str) -> User:
    """Same checks as authenticate_user, plus requires the admin role.
    Use for user management, hospital management, and any other
    admin-only action."""
    user = authenticate_user(db, user_id, email, auth_token)
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


def authenticate_staff_or_admin(db: Session, user_id: int, email: str, auth_token: str) -> User:
    """Same checks as authenticate_user, plus requires staff or admin
    role. Use for admissions, discharges, transfers, forecast lookups."""
    user = authenticate_user(db, user_id, email, auth_token)
    if user.role not in (UserRole.admin, UserRole.staff):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Staff or admin access required.")
    return user


def check_staff_hospital_match(user: User, hospital_id: int) -> None:
    """
    Given an already-authenticated user, blocks the action if they're
    staff assigned to a DIFFERENT hospital than hospital_id. Admins
    aren't tied to one hospital and are never blocked here. Use this
    when the target hospital_id is only known after fetching a
    resource (e.g. an admission's hospital_id), so the token only
    gets verified once via authenticate_staff_or_admin, and this just
    does the cheap in-memory hospital check on top.
    """
    if user.role == UserRole.staff and user.hospital_id != hospital_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="You can only manage patients at your assigned hospital.",
        )


def authenticate_staff_for_hospital(db: Session, user_id: int, email: str, auth_token: str, hospital_id: int) -> User:
    """
    Same as authenticate_staff_or_admin, plus enforces that staff can
    only act on their own assigned hospital. Use this when hospital_id
    is already known upfront (e.g. admitting a patient, where the
    target hospital is part of the request itself).
    """
    user = authenticate_staff_or_admin(db, user_id, email, auth_token)
    check_staff_hospital_match(user, hospital_id)
    return user
