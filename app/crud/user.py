from typing import List, Optional, TypedDict

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.otp_service import OTP_VALIDITY_MINUTES
from app.services.token_service import AUTH_TOKEN_VALIDITY_DAYS


class OtpStatus(TypedDict):
    otp: Optional[int]
    is_not_expired: bool


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.user_id == user_id).first()


def list_all_users(db: Session) -> List[User]:
    return db.query(User).order_by(User.user_id).all()


def create_user(db: Session, email: str, role: UserRole, hospital_id: Optional[int] = None) -> User:
    """
    Provisions a new account. Accounts here are always created
    deliberately, either by the bootstrap script (first admin) or by
    an admin creating an account through the API, never by someone
    self-registering with an arbitrary email.
    """
    user = User(email=email, role=role, hospital_id=hospital_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session, user: User, role: Optional[UserRole] = None, hospital_id: Optional[int] = None
) -> User:
    if role is not None:
        user.role = role
    if hospital_id is not None:
        user.hospital_id = hospital_id
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()


def set_user_otp(db: Session, user: User, otp: int) -> User:
    """Save the OTP and set its expiry using the MySQL server's own clock
    (NOW()), avoiding drift between the app server and DB server clocks."""
    db.execute(
        text(
            "UPDATE users "
            f"SET otp = :otp, otp_exp_time = NOW() + INTERVAL {OTP_VALIDITY_MINUTES} MINUTE "
            "WHERE user_id = :user_id"
        ),
        {"otp": otp, "user_id": user.user_id},
    )
    db.commit()
    db.refresh(user)
    return user


def get_otp_status(db: Session, user: User) -> OtpStatus:
    """Read back the stored OTP and whether it's still valid, comparing
    expiry against the MySQL server's own clock (NOW())."""
    row = (
        db.execute(
            text(
                "SELECT otp, (otp_exp_time IS NOT NULL AND otp_exp_time >= NOW()) AS is_not_expired "
                "FROM users WHERE user_id = :user_id"
            ),
            {"user_id": user.user_id},
        )
        .mappings()
        .first()
    )
    return {"otp": row["otp"], "is_not_expired": bool(row["is_not_expired"])}


def set_auth_token(db: Session, user: User, auth_token: str) -> User:
    """Save the auth token, set its expiry via the DB clock, and clear the
    now-consumed OTP fields."""
    db.execute(
        text(
            "UPDATE users "
            f"SET auth_token = :auth_token, auth_token_exp_time = NOW() + INTERVAL {AUTH_TOKEN_VALIDITY_DAYS} DAY, "
            "otp = NULL, otp_exp_time = NULL "
            "WHERE user_id = :user_id"
        ),
        {"auth_token": auth_token, "user_id": user.user_id},
    )
    db.commit()
    db.refresh(user)
    return user
