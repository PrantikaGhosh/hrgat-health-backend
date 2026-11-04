import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.utils import format_exception


class EmailSendError(Exception):
    """Raised when the OTP email could not be delivered via SMTP."""


def send_otp_email(to_email: str, otp: int) -> None:
    message = MIMEMultipart()
    message["From"] = settings.SMTP_USERNAME
    message["To"] = to_email
    message["Subject"] = "Your HRGAT-Health Login OTP"
    message.attach(
        MIMEText(
            f"Your OTP for login is: {otp}\n"
            "This OTP is valid for 5 minutes.\n\n"
            "If you did not request this, please ignore this email.",
            "plain",
        )
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USERNAME, [to_email], message.as_string())
    except smtplib.SMTPAuthenticationError as exc:
        raise EmailSendError(
            f"SMTP authentication failed — check SMTP_USERNAME/SMTP_PASSWORD ({format_exception(exc)})"
        ) from exc
    except smtplib.SMTPException as exc:
        raise EmailSendError(f"SMTP error while sending OTP email — {format_exception(exc)}") from exc
    except (OSError, TimeoutError) as exc:
        raise EmailSendError(
            f"Could not reach SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT} — {format_exception(exc)}"
        ) from exc
