from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin_hospitals import router as admin_hospitals_router
from app.api.routes.admin_users import router as admin_users_router
from app.api.routes.admissions import router as admissions_router
from app.api.routes.auth import router as auth_router
from app.api.routes.forecast import router as forecast_router
from app.api.routes.hospitals import hrr_router, router as hospitals_router
from app.api.routes.patients import router as patients_router
from app.db.init_db import check_db_connection, create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_db_connection()
    create_tables()
    yield


app = FastAPI(title="HRGAT-Health API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_users_router)
app.include_router(admin_hospitals_router)
app.include_router(hospitals_router)
app.include_router(hrr_router)
app.include_router(patients_router)
app.include_router(admissions_router)
app.include_router(forecast_router)


@app.get("/")
def root():
    return {"message": "HRGAT-Health API is running"}
