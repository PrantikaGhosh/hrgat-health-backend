"""
Seed the Hospital and HospitalEdge tables from the ML pipeline's real
Texas hospital data (369 hospitals, referral-network edges).

Run once, after the auth system is already set up:
    python scripts/seed_hospitals.py
"""

import sys
sys.path.append(".")

import pandas as pd

from app.db.init_db import check_db_connection, create_tables
from app.db.session import SessionLocal
from app.models.hospital import Hospital, HospitalEdge

NODES_PATH = "data/processed/hospital_nodes.csv"
EDGES_PATH = "data/processed/hospital_edges.csv"
PANEL_PATH = "data/processed/texas_panel_graph_ready.csv"

check_db_connection()
create_tables()

db = SessionLocal()

if db.query(Hospital).count() > 0:
    print("Hospitals table is not empty, skipping seed.")
    print("(Delete existing rows first if you want to reseed from scratch.)")
    db.close()
    sys.exit(0)

nodes = pd.read_csv(NODES_PATH, dtype={"hospital_pk": str})
panel = pd.read_csv(PANEL_PATH, dtype={"hospital_pk": str}, low_memory=False)

# Most recent known bed capacity per hospital, used for occupancy denominators
latest = panel.sort_values("collection_week").groupby("hospital_pk").tail(1).set_index("hospital_pk")

print(f"Seeding {len(nodes)} hospitals...")
hospital_pk_to_id = {}
for _, row in nodes.iterrows():
    hospital_pk = row["hospital_pk"]
    panel_row = latest.loc[hospital_pk] if hospital_pk in latest.index else None

    hospital = Hospital(
        hospital_pk=hospital_pk,
        name=str(panel_row["hospital_name"]) if panel_row is not None else hospital_pk,
        city=str(panel_row["city"]) if panel_row is not None and pd.notna(panel_row["city"]) else None,
        state="TX",
        hrr_id=int(row["hrrnum"]),
        hrr_city=row["hrrcity"],
        total_beds=int(panel_row["total_beds_7_day_avg"])
        if panel_row is not None and pd.notna(panel_row["total_beds_7_day_avg"])
        else None,
        total_icu_beds=int(panel_row["total_icu_beds_7_day_avg"])
        if panel_row is not None and pd.notna(panel_row["total_icu_beds_7_day_avg"])
        else None,
    )
    db.add(hospital)
    db.flush()  # assigns hospital.hospital_id before the final commit
    hospital_pk_to_id[hospital_pk] = hospital.hospital_id

db.commit()
print(f"Seeded {len(hospital_pk_to_id)} hospitals.")

print("Seeding referral-network edges...")
edges = pd.read_csv(EDGES_PATH, dtype={"source": str, "target": str})
count = 0
for _, row in edges.iterrows():
    source_id = hospital_pk_to_id.get(row["source"])
    target_id = hospital_pk_to_id.get(row["target"])
    if source_id and target_id:
        db.add(HospitalEdge(source_hospital_id=source_id, target_hospital_id=target_id))
        count += 1

db.commit()
print(f"Seeded {count} edges.")
db.close()
print("\nDone. Hospitals are now available via GET /hospitals.")
