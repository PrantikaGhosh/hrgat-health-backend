"""
One-time migration: fixes foreign key ON DELETE behavior for
databases created before this change. Safe to run multiple times,
doesn't touch or lose any existing data, only alters the constraint
definitions themselves.

- admissions.admitted_by_user_id -> users.user_id: changed to
  ON DELETE SET NULL, so removing a staff account isn't blocked by
  their historical admission records.
- hospital_edges.source_hospital_id / target_hospital_id ->
  hospitals.hospital_id: changed to ON DELETE CASCADE, an edge can't
  meaningfully exist without both its hospitals, so removing a
  hospital should remove its graph connections too.

admissions.hospital_id is deliberately left alone (still blocks
deletion), see the /admin/hospitals DELETE endpoint for why.

Run from backend/ with venv active:
    python scripts/fix_fk_constraints.py
"""

import sys
sys.path.append(".")

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine


def get_constraint_name(conn, table_name, column_name):
    result = conn.execute(
        text(
            """
            SELECT CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = :schema
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
              AND REFERENCED_TABLE_NAME IS NOT NULL
            """
        ),
        {"schema": settings.DB_NAME, "table_name": table_name, "column_name": column_name},
    )
    row = result.fetchone()
    return row[0] if row else None


def fix_constraint(conn, table_name, column_name, referenced_table, referenced_column, on_delete):
    constraint_name = get_constraint_name(conn, table_name, column_name)
    if constraint_name is None:
        print(f"  No FK found for {table_name}.{column_name}, skipping.")
        return
    print(f"  {table_name}.{column_name}: rebuilding '{constraint_name}' with ON DELETE {on_delete}...")
    conn.execute(text(f"ALTER TABLE {table_name} DROP FOREIGN KEY {constraint_name}"))
    conn.execute(
        text(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
            f"FOREIGN KEY ({column_name}) REFERENCES {referenced_table}({referenced_column}) "
            f"ON DELETE {on_delete}"
        )
    )


def main():
    with engine.begin() as conn:
        print("Fixing admissions.admitted_by_user_id -> users.user_id (SET NULL)...")
        fix_constraint(conn, "admissions", "admitted_by_user_id", "users", "user_id", "SET NULL")

        print("Fixing hospital_edges.source_hospital_id -> hospitals.hospital_id (CASCADE)...")
        fix_constraint(conn, "hospital_edges", "source_hospital_id", "hospitals", "hospital_id", "CASCADE")

        print("Fixing hospital_edges.target_hospital_id -> hospitals.hospital_id (CASCADE)...")
        fix_constraint(conn, "hospital_edges", "target_hospital_id", "hospitals", "hospital_id", "CASCADE")

    print("\nDone. No data was modified, only constraint behavior.")


if __name__ == "__main__":
    main()
