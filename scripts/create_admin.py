"""
Run once to create the first admin account: admin@email.com.

No password needed, the whole system is passwordless (OTP-over-email).
After this runs, that account logs in normally through
POST /auth/login-request and POST /auth/verify-otp, and can then use
the /admin/users endpoints to create every other admin and staff
account, no more manual scripts needed after this one.

Run from backend/ with venv active:
    python scripts/create_admin.py
"""

import sys
sys.path.append(".")

from app.db.init_db import check_db_connection, create_tables
from app.db.session import SessionLocal
from app.crud.user import get_user_by_email, create_user
from app.models.user import UserRole

ADMIN_EMAIL = "admin@email.com"

check_db_connection()
create_tables()

db = SessionLocal()

existing = get_user_by_email(db, ADMIN_EMAIL)
if existing:
    print(f"An account already exists for '{ADMIN_EMAIL}' (role: {existing.role.value}).")
else:
    admin = create_user(db, email=ADMIN_EMAIL, role=UserRole.admin)
    print(f"Admin account created for '{ADMIN_EMAIL}'.")
    print("Log in via POST /auth/login-request with this email to receive an OTP.")

db.close()
