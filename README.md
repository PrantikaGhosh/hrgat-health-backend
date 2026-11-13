# HRGAT-Health Backend

FastAPI backend and research pipeline for **HRGAT-Health**: Hospital Referral-Network-Aware Spatio-Temporal Graph Attention Network for ICU and Bed Occupancy Forecasting.

The project forecasts next-week ICU and general bed occupancy for 369 Texas hospitals. Hospitals are linked into a graph through the Dartmouth Atlas Hospital Referral Regions (HRR). The STGAT model combines graph attention over referral neighbors with a GRU over the last 8 weeks and a persistence anchor. The backend serves the trained models through a REST API with live hospital operations.

## Features

- **STGAT forecasting** for ICU and general beds, with naive, ARIMA and LSTM baselines
- **Referral network graph**: 369 hospitals, 24 referral regions, 6,250 edges
- **Passwordless login**: e-mail OTP with token-based sessions
- **Roles**: admins manage accounts and hospitals, staff act only on their own hospital
- **Patient flow**: admit, discharge and transfer, with capacity checks
- **Capacity guard**: admissions to a full unit are blocked with a referral hint
- **Transfer suggestions**: hospitals in the same referral region with free beds
- **Live-aware forecast**: the forecast updates after every patient action

## Results (test set)

| Target | Model | RMSE | MAE | MAPE (%) |
|---|---|---|---|---|
| ICU beds | Naive (persistence) | 4.142 | 1.317 | 13.08 |
| ICU beds | ARIMA(2,1,2) | 3.865 | 1.385 | 16.99 |
| ICU beds | LSTM | 4.099 | 1.418 | 22.70 |
| ICU beds | **STGAT** | 4.140 | 1.335 | 14.19 |
| General beds | Naive (persistence) | 23.662 | 7.401 | 29.96 |
| General beds | ARIMA(2,1,2) | 22.806 | 7.767 | 36.56 |
| General beds | LSTM | 25.612 | 8.818 | 111.46 |
| General beds | **STGAT** | 23.740 | 7.630 | 36.86 |

STGAT gives 37.5% lower ICU MAPE than the LSTM and 16.5% lower than ARIMA. It has the lowest MAE of the trained models on both targets, with only 473 parameters.

## Tech stack

- **API**: FastAPI, Uvicorn, Pydantic
- **Database**: MySQL with SQLAlchemy and PyMySQL
- **ML**: PyTorch, PyTorch Geometric, statsmodels, pandas, NumPy

## Project structure

```
backend/
├── app/
│   ├── api/routes/      # auth, admin users, admin hospitals, hospitals, patients, admissions, forecast
│   ├── core/            # config (.env loading), utils
│   ├── crud/            # database queries
│   ├── db/              # session, auto database and table creation
│   ├── models/          # users, hospitals, hospital_edges, patients, admissions
│   ├── schemas/         # request and response models
│   ├── services/        # OTP, e-mail, auth guard, forecast service
│   └── main.py
├── data/processed/      # cleaned panel, graph files, model datasets, normalization stats
├── saved_models/        # trained STGAT and LSTM weights (ICU and beds)
├── scripts/             # create_admin, seed_hospitals, fix_fk_constraints, check_capacity_history
├── src/                 # research pipeline: data_pipeline, graph, models, training
├── API_DOCUMENTATION.md
├── requirements.txt
└── .env.sample
```

## Setup

### Prerequisites

- Python 3.10 or newer
- MySQL 8 running locally or on a server
- An SMTP account for sending login codes

### 1. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.sample .env
```

Fill in the database and SMTP values in `.env`. The database itself is created automatically if it does not exist. Never commit `.env`.

### 3. Create the first admin

```bash
python scripts/create_admin.py
```

This creates the database, all tables and the admin account `admin@email.com`. The admin logs in with the normal OTP flow and adds every other admin and staff account from the Team page.

### 4. Load the hospitals

```bash
python scripts/seed_hospitals.py
```

This loads the 369 Texas hospitals and 6,250 referral edges from `data/processed/`. A second run does nothing, so it never creates duplicates.

### 5. Run

```bash
uvicorn app.main:app --reload
```

- API: `http://127.0.0.1:8000`
- Interactive docs: `http://127.0.0.1:8000/docs`

### Check the setup

```sql
SELECT COUNT(*) FROM hospitals;       -- 369
SELECT COUNT(*) FROM hospital_edges;  -- 6250
SELECT email, role FROM users;
```

## API overview

Full details with curl and Postman samples are in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login-request`, `POST /auth/verify-otp` |
| Admin users | `POST/GET /admin/users`, `GET/PATCH/DELETE /admin/users/{id}` |
| Admin hospitals | `POST /admin/hospitals`, `PATCH/DELETE /admin/hospitals/{id}` |
| Hospitals | `GET /hospitals`, `GET /hospitals/{id}`, `/neighbors`, `/transfer-options`, `/occupancy`, `/patients`, `/forecast`, `/history` |
| Regions | `GET /hrr/{hrr_id}/hospitals` |
| Patients | `GET /patients/{id}` |
| Admissions | `POST /admissions`, `POST /admissions/{id}/discharge`, `POST /admissions/{id}/transfer` |
| Forecast | `GET /forecast/all` |

Every protected request carries `user_id`, `email` and `auth_token`. A `401` means the session is invalid or expired; a `403` means the role or hospital does not allow the action. A `409` on admission means the unit is full.

## Research pipeline

The trained models and processed data are already in the repo, so the API runs without retraining. To rebuild from scratch, download the raw files into `data/raw/` (this folder is not tracked):

- HHS "COVID-19 Reported Patient Impact and Hospital Capacity by Facility (RAW)", dataset `uqq2-txqb` on HealthData.gov
- Dartmouth Atlas hospital to HSA/HRR crosswalk

Then run the scripts in this order:

1. `src/data_pipeline/`: inspect, filter, clean, check reporting consistency, build the final panel, build the HRR mapping and the graph
2. `src/training/`: windows, naive and ARIMA baselines, LSTM dataset and training (`_icu` and `_beds` versions)
3. `src/graph/prepare_stgat_dataset_*.py`, then `src/training/train_stgat_*.py`

## Notes

- `scripts/fix_fk_constraints.py` is only needed for databases created before the foreign key rules changed. A fresh setup already has the right rules.
- The OTP is valid for 5 minutes.

## Team

Prantika Ghosh, Pijush Banerjee, Rishita Paul, Priyanshu Ghosh, Veerat Pandey

Under the guidance of Prof. (Dr.) Sudipta Sahana, Department of CSE (AI & ML), University of Engineering and Management, Kolkata.
