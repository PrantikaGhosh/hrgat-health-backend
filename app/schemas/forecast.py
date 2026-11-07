from typing import List

from pydantic import BaseModel


class ForecastResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    target: str
    predicted_value: float
    based_on_week: str
    predicted_week: str


class ForecastAllItem(BaseModel):
    hospital_id: int
    hospital_name: str
    predicted_value: float


class ForecastAllResponse(BaseModel):
    target: str
    based_on_week: str
    count: int
    forecasts: List[ForecastAllItem]


class HistoryPoint(BaseModel):
    week: str
    value: float


class HistoryResponse(BaseModel):
    hospital_id: int
    hospital_name: str
    target: str
    history: List[HistoryPoint]
