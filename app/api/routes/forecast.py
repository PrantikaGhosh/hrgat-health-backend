from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.utils import format_exception
from app.crud.hospital import list_all_hospitals
from app.schemas.forecast import ForecastAllItem, ForecastAllResponse
from app.services.auth_guard import authenticate_staff_or_admin
from app.services.forecast_service import get_forecast_for_all_hospitals

router = APIRouter(prefix="/forecast", tags=["Forecast"])


@router.get("/all", response_model=ForecastAllResponse)
def forecast_all(
    user_id: int, email: str, auth_token: str, target: str = "icu", db: Session = Depends(get_db)
) -> ForecastAllResponse:
    authenticate_staff_or_admin(db, user_id, email, auth_token)
    if target not in ("icu", "beds"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="target must be 'icu' or 'beds'.")

    try:
        predictions, last_week = get_forecast_for_all_hospitals(target)
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Model or data file missing — {format_exception(exc)}"
        ) from exc

    hospitals = list_all_hospitals(db)
    items = [
        ForecastAllItem(hospital_id=h.hospital_id, hospital_name=h.name, predicted_value=round(predictions[h.hospital_pk], 2))
        for h in hospitals
        if h.hospital_pk and h.hospital_pk in predictions
    ]

    return ForecastAllResponse(target=target, based_on_week=str(last_week.date()), count=len(items), forecasts=items)
