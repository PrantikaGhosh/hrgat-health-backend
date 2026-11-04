from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.user import get_otp_status, get_user_by_email, set_auth_token, set_user_otp
from app.schemas.auth import LoginRequest, LoginResponse, VerifyOtpRequest, VerifyOtpResponse
from app.services.email_service import EmailSendError, send_otp_email
from app.services.otp_service import generate_otp
from app.services.token_service import generate_auth_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login-request", response_model=LoginResponse, status_code=status.HTTP_200_OK)
def login_request(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    try:
        user = get_user_by_email(db, payload.email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while looking up user — {format_exception(exc)}",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found for this email. Contact your administrator.",
        )

    otp = generate_otp()

    try:
        set_user_otp(db, user, otp)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving OTP — {format_exception(exc)}",
        ) from exc

    try:
        send_otp_email(payload.email, otp)
    except EmailSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OTP generated but could not be emailed — {format_exception(exc)}",
        ) from exc

    return LoginResponse(message="OTP sent successfully", email=payload.email)


@router.post("/verify-otp", response_model=VerifyOtpResponse, status_code=status.HTTP_200_OK)
def verify_otp(payload: VerifyOtpRequest, db: Session = Depends(get_db)) -> VerifyOtpResponse:
    try:
        user = get_user_by_email(db, payload.email)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while looking up user — {format_exception(exc)}",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found. Please request an OTP first.",
        )

    try:
        otp_status = get_otp_status(db, user)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while verifying OTP — {format_exception(exc)}",
        ) from exc

    if otp_status["otp"] is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested for this email. Please request an OTP first.",
        )

    if otp_status["otp"] != payload.otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid OTP.")

    if not otp_status["is_not_expired"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new OTP.",
        )

    auth_token = generate_auth_token()
    try:
        user = set_auth_token(db, user, auth_token)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error while saving auth token — {format_exception(exc)}",
        ) from exc

    return VerifyOtpResponse(
        message="OTP verified successfully",
        user_id=user.user_id,
        email=user.email,
        role=user.role.value,
        hospital_id=user.hospital_id,
        auth_token=user.auth_token,
        auth_token_exp_time=user.auth_token_exp_time,
    )
