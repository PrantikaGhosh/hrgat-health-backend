import enum

from sqlalchemy import Column, DateTime, Enum, Integer, SmallInteger, String

from app.db.session import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    staff = "staff"


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(50), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.staff)
    # Staff are tied to the hospital they work at. Nullable since admins
    # aren't tied to one hospital. Plain column for now (no FK constraint
    # yet), the Hospital table gets built in the next step.
    hospital_id = Column(Integer, nullable=True)

    otp = Column(SmallInteger, nullable=True)
    otp_exp_time = Column(DateTime, nullable=True)
    auth_token = Column(String(36), nullable=True)
    auth_token_exp_time = Column(DateTime, nullable=True)
