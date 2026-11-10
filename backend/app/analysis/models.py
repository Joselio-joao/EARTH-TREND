from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ObservationInput(BaseModel):
    date: date
    value: float


class AnalyzeRequest(BaseModel):
    investigation_id: str = Field(min_length=1)
    data_origin: Literal["synthetic_test", "scientific_dataset"]
    unit: str = Field(min_length=1)
    observations: list[ObservationInput] = Field(min_length=3)


class AnalyzeResponse(BaseModel):
    investigation_id: str
    data_origin: str
    unit: str
    n_observations: int
    slope_per_year: float
    sen_slope_per_year: float
    r_squared: float
    mann_kendall_s: int
    mann_kendall_z: float
    p_value: float
    direction: str
    statistically_significant: bool
    limitations: list[str]
