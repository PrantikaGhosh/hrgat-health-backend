import sys

import pymysql
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.db.session import Base, engine


def _ensure_database_exists() -> None:
    connection = pymysql.connect(
        host=settings.DB_HOST,
        port=int(settings.DB_PORT),
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        connection.commit()
    finally:
        connection.close()


def check_db_connection() -> None:
    try:
        _ensure_database_exists()
        with engine.connect():
            pass
        print(
            f"[DB] Connected to MySQL database '{settings.DB_NAME}' "
            f"at {settings.DB_HOST}:{settings.DB_PORT}"
        )
    except pymysql.err.OperationalError as exc:
        print(f"[DB] Could not reach MySQL server at {settings.DB_HOST}:{settings.DB_PORT} — {exc}")
        sys.exit(1)
    except OperationalError as exc:
        print(f"[DB] Failed to connect to database '{settings.DB_NAME}' — {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"[DB] Unexpected error while connecting to MySQL — {exc}")
        sys.exit(1)


def create_tables() -> None:
    from app import models  # noqa: F401 - registers models on Base.metadata

    try:
        Base.metadata.create_all(bind=engine)
        print("[DB] Tables verified/created successfully.")
    except Exception as exc:
        print(f"[DB] Failed to create tables — {exc}")
        sys.exit(1)
