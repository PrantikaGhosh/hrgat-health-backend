# HRGAT-Health API Documentation

Base URL (local development): `http://127.0.0.1:8000`

**Last updated:** covers Auth, Admin User Management, Hospitals, Admin
Hospital Management, Patients, Admissions, and Forecast endpoints.
This file is updated every time new endpoints are added. Import any curl
command below directly into Postman (File → Import → Raw text) to get a
ready-made request.

---

## Authentication model

This API is **passwordless**. There are no passwords and no bearer tokens
in headers. Instead:

1. You request a one-time OTP sent to your email.
2. You verify that OTP and receive an `auth_token` (a UUID string) plus
   your `user_id`.
3. Every protected endpoint after that requires you to send back your
   `user_id`, `email`, and `auth_token` explicitly (in the JSON body for
   POST/PATCH requests, as query parameters for GET/DELETE requests). The
   server re-verifies all three on every single call.

Tokens expire after 7 days. OTPs expire after 5 minutes.

**Role levels used below:**
- **None** — publicly accessible, no login needed
- **Any logged-in user** — valid `user_id`/`email`/`auth_token`, admin or staff
- **Staff or admin** — same, but the account's role must be `staff` or `admin`
- **Admin only** — the account's role must be `admin`

---

## Auth endpoints

### `POST /auth/login-request`

Request an OTP be emailed to an existing account. **The email must
already exist as a user**, there is no public self-registration.

**Auth required:** none

**Request body:**
```json
{ "email": "admin@email.com" }
```

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/auth/login-request \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@email.com"}'
```

**Success — `200 OK`:**
```json
{ "message": "OTP sent successfully", "email": "admin@email.com" }
```

**Errors:**
| Status | Cause |
|---|---|
| 404 | Email has no account |
| 502 | OTP generated but SMTP send failed |
| 500 | Database error |

---

### `POST /auth/verify-otp`

Verify the OTP and receive an auth token.

**Auth required:** none

**Request body:**
```json
{ "email": "admin@email.com", "otp": 1234 }
```

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@email.com", "otp": 1234}'
```

**Success — `200 OK`:**
```json
{
  "message": "OTP verified successfully",
  "user_id": 1,
  "email": "admin@email.com",
  "role": "admin",
  "hospital_id": null,
  "auth_token": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "auth_token_exp_time": "2026-08-27T10:15:00"
}
```

**Errors:**
| Status | Cause |
|---|---|
| 404 | Email not found |
| 400 | No OTP requested yet, or OTP expired |
| 401 | Wrong OTP |

---

## Admin — User Management
*(all require admin auth fields, all return 403 if caller isn't admin)*

### `POST /admin/users` — create an admin or staff account

**Request body:**
```json
{
  "user_id": 1, "email": "admin@email.com", "auth_token": "3fa85f64-...",
  "new_user_email": "staffmember@email.com", "role": "staff", "hospital_id": 1
}
```
`hospital_id` required when `role` is `"staff"`.

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/admin/users \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"email":"admin@email.com","auth_token":"3fa85f64-...","new_user_email":"staffmember@email.com","role":"staff","hospital_id":1}'
```

**Success — `201 Created`:**
```json
{
  "message": "Staff account created for 'staffmember@email.com'.",
  "user": {"user_id": 2, "email": "staffmember@email.com", "role": "staff", "hospital_id": 1}
}
```

**Errors:** `400` invalid role/missing hospital_id · `403` not admin · `409` email already exists

---

### `GET /admin/users` — list every account

**curl:**
```bash
curl -G http://127.0.0.1:8000/admin/users \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

**Success — `200 OK`:**
```json
{"count": 2, "users": [
  {"user_id": 1, "email": "admin@email.com", "role": "admin", "hospital_id": null},
  {"user_id": 2, "email": "staffmember@email.com", "role": "staff", "hospital_id": 1}
]}
```

---

### `GET /admin/users/{target_user_id}` — one account's detail

**curl:**
```bash
curl -G http://127.0.0.1:8000/admin/users/2 \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```
**Errors:** `404` if not found.

---

### `PATCH /admin/users/{target_user_id}` — change role/hospital

**Request body:**
```json
{"user_id":1,"email":"admin@email.com","auth_token":"3fa85f64-...","hospital_id":3}
```

---

### `DELETE /admin/users/{target_user_id}` — remove an account

**curl:**
```bash
curl -X DELETE "http://127.0.0.1:8000/admin/users/2" -G \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```
**Errors:** `400` trying to delete your own logged-in account · `404` not found

---

## Hospitals
*(list/detail/neighbors/HRR require any logged-in user; occupancy/patients/forecast/history require staff or admin)*

### `GET /hospitals` — list all hospitals

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

**Success — `200 OK`:**
```json
{"count": 369, "hospitals": [
  {"hospital_id": 1, "hospital_pk": "450034", "name": "Example Medical Center",
   "city": "Houston", "state": "TX", "hrr_id": 391, "hrr_city": "Houston",
   "total_beds": 320, "total_icu_beds": 40}
]}
```

---

### `GET /hospitals/{hospital_id}` — one hospital's detail

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1 \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```
**Errors:** `404` not found

---

### `GET /hospitals/{hospital_id}/neighbors` — referral-connected hospitals

Hospitals sharing the same Hospital Referral Region (HRR).

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1/neighbors \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

---

### `GET /hrr/{hrr_id}/hospitals` — all hospitals in one referral region

**curl:**
```bash
curl -G http://127.0.0.1:8000/hrr/391/hospitals \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

---

### `GET /hospitals/{hospital_id}/occupancy` — live bed occupancy snapshot

Computed in real time from active (not yet discharged/transferred) admissions.

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1/occupancy \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

**Success — `200 OK`:**
```json
{
  "hospital_id": 1, "hospital_name": "Example Medical Center",
  "total_beds": 320, "total_icu_beds": 40,
  "occupied_general": 12, "occupied_icu": 3,
  "available_general": 308, "available_icu": 37
}
```
**Errors:** `404` not found

---

### `GET /hospitals/{hospital_id}/patients` — currently admitted patients

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1/patients \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```

---

### `GET /hospitals/{hospital_id}/forecast` — next-week prediction

Uses the trained STGAT model. **Note:** built from the most recent 8
weeks of real historical training data (through April 2024), not live
occupancy, a documented demo simplification — see `forecast_service.py`.

**Query params:** `user_id`, `email`, `auth_token`, `target` (`"icu"` or `"beds"`, default `"icu"`)

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1/forecast \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..." --data-urlencode "target=icu"
```

**Success — `200 OK`:**
```json
{
  "hospital_id": 1, "hospital_name": "Example Medical Center",
  "target": "icu", "predicted_value": 5.42, "based_on_week": "2024-04-21"
}
```
**Errors:** `400` invalid target, or hospital not part of trained model · `404` not found / no forecast available

---

### `GET /hospitals/{hospital_id}/history` — historical weekly series (for charts)

**Query params:** `user_id`, `email`, `auth_token`, `target` (default `"icu"`), `weeks` (default `26`)

**curl:**
```bash
curl -G http://127.0.0.1:8000/hospitals/1/history \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..." --data-urlencode "target=icu" --data-urlencode "weeks=12"
```

**Success — `200 OK`:**
```json
{
  "hospital_id": 1, "hospital_name": "Example Medical Center", "target": "icu",
  "history": [{"week": "2024-02-04", "value": 4.1}, {"week": "2024-02-11", "value": 4.6}]
}
```

---

## Admin — Hospital Management
*(admin only)*

### `POST /admin/hospitals` — add a hospital

**Note:** manually added hospitals have `hospital_pk: null` and therefore
**no forecast available** (they weren't part of the trained model).

**Request body:**
```json
{
  "user_id": 1, "email": "admin@email.com", "auth_token": "3fa85f64-...",
  "name": "New Community Hospital", "city": "Austin", "state": "TX",
  "hrr_id": 385, "hrr_city": "Austin", "total_beds": 150, "total_icu_beds": 20
}
```

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/admin/hospitals \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"email":"admin@email.com","auth_token":"3fa85f64-...","name":"New Community Hospital","city":"Austin","state":"TX","hrr_id":385,"hrr_city":"Austin","total_beds":150,"total_icu_beds":20}'
```

**Success — `201 Created`:**
```json
{
  "message": "Hospital 'New Community Hospital' created. Note: manually added hospitals have no forecast available since they weren't part of the trained model.",
  "hospital": {"hospital_id": 370, "hospital_pk": null, "name": "New Community Hospital", "city": "Austin", "state": "TX", "hrr_id": 385, "hrr_city": "Austin", "total_beds": 150, "total_icu_beds": 20}
}
```

---

### `PATCH /admin/hospitals/{hospital_id}` — edit hospital info

**Request body:** any subset of the create fields, plus auth fields.
```json
{"user_id":1,"email":"admin@email.com","auth_token":"3fa85f64-...","total_beds":160}
```
**Errors:** `404` not found

---

### `DELETE /admin/hospitals/{hospital_id}` — remove a hospital

**curl:**
```bash
curl -X DELETE "http://127.0.0.1:8000/admin/hospitals/370" -G \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..."
```
**Errors:** `404` not found

---

## Patients
*(staff or admin)*

### `GET /patients/{patient_id}` — patient detail

**curl:**
```bash
curl -G http://127.0.0.1:8000/patients/1 \
  --data-urlencode "user_id=2" --data-urlencode "email=staffmember@email.com" \
  --data-urlencode "auth_token=<staff-token>"
```

**Success — `200 OK`:**
```json
{"patient_id": 1, "name": "Jane Doe", "age": 54, "gender": "female", "created_at": "2026-08-20T10:00:00"}
```
**Errors:** `404` not found

---

## Admissions
*(staff or admin)*

### `POST /admissions` — admit a patient

Creates a new patient record and an active admission in one call.

**Request body:**
```json
{
  "user_id": 2, "email": "staffmember@email.com", "auth_token": "<staff-token>",
  "hospital_id": 1, "patient_name": "Jane Doe", "age": 54, "gender": "female",
  "bed_type": "icu"
}
```
`bed_type` must be `"icu"` or `"general"`.

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/admissions \
  -H "Content-Type: application/json" \
  -d '{"user_id":2,"email":"staffmember@email.com","auth_token":"<staff-token>","hospital_id":1,"patient_name":"Jane Doe","age":54,"gender":"female","bed_type":"icu"}'
```

**Success — `201 Created`:**
```json
{
  "message": "Patient admitted to 'Example Medical Center'.",
  "admission": {"admission_id": 1, "patient_id": 1, "hospital_id": 1, "bed_type": "icu", "status": "admitted", "admit_time": "2026-08-20T10:00:00", "discharge_time": null}
}
```
**Errors:** `400` invalid bed_type · `404` hospital not found

---

### `POST /admissions/{admission_id}/discharge` — discharge a patient

**Request body:**
```json
{"user_id":2,"email":"staffmember@email.com","auth_token":"<staff-token>"}
```

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/admissions/1/discharge \
  -H "Content-Type: application/json" \
  -d '{"user_id":2,"email":"staffmember@email.com","auth_token":"<staff-token>"}'
```
**Errors:** `400` already discharged/transferred · `404` admission not found

---

### `POST /admissions/{admission_id}/transfer` — transfer to another hospital

Marks the current admission `transferred`, creates a fresh `admitted`
admission at the destination hospital, linked via `transferred_from_admission_id`.

**Request body:**
```json
{"user_id":2,"email":"staffmember@email.com","auth_token":"<staff-token>","destination_hospital_id":5}
```

**curl:**
```bash
curl -X POST http://127.0.0.1:8000/admissions/1/transfer \
  -H "Content-Type: application/json" \
  -d '{"user_id":2,"email":"staffmember@email.com","auth_token":"<staff-token>","destination_hospital_id":5}'
```

**Success — `200 OK`:**
```json
{
  "message": "Patient transferred to 'Another Hospital'.",
  "admission": {"admission_id": 2, "patient_id": 1, "hospital_id": 5, "bed_type": "icu", "status": "admitted", "admit_time": "2026-08-20T11:00:00", "discharge_time": null}
}
```
**Errors:** `400` already discharged/transferred, or destination same as current · `404` admission or destination not found

---

## Forecast
*(staff or admin)*

### `GET /forecast/all` — predictions for every hospital in one call

**Query params:** `user_id`, `email`, `auth_token`, `target` (`"icu"` or `"beds"`, default `"icu"`)

**curl:**
```bash
curl -G http://127.0.0.1:8000/forecast/all \
  --data-urlencode "user_id=1" --data-urlencode "email=admin@email.com" \
  --data-urlencode "auth_token=3fa85f64-..." --data-urlencode "target=icu"
```

**Success — `200 OK`:**
```json
{
  "target": "icu", "based_on_week": "2024-04-21", "count": 369,
  "forecasts": [
    {"hospital_id": 1, "hospital_name": "Example Medical Center", "predicted_value": 5.42},
    {"hospital_id": 2, "hospital_name": "Another Hospital", "predicted_value": 2.10}
  ]
}
```

---

## System

### `GET /`

**curl:** `curl http://127.0.0.1:8000/`
**Response:** `{"message": "HRGAT-Health API is running"}`

---

## Setup scripts (not HTTP endpoints)

- `python scripts/create_admin.py` — bootstraps the first admin account (`admin@email.com`)
- `python scripts/seed_hospitals.py` — populates the 369 real Texas hospitals + referral-network edges from the ML pipeline's data

---

## Backend status

All planned endpoints from the original design are now built: Auth,
Admin User Management, Hospitals, Admin Hospital Management, Patients,
Admissions, and Forecast. Remaining work is the frontend dashboard,
which consumes this API.
