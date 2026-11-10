from datetime import date
from uuid import uuid4

from pydantic import BaseModel, Field

from app.datasets import DATASETS
from app.regions import PROVINCES


class InvestigationRequest(BaseModel):
    country_id: str = Field(default="angola", min_length=1)
    province_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    start_date: date
    end_date: date


class InvestigationRecord(BaseModel):
    id: str
    status: str
    analysis_status: str
    country_id: str
    province_id: str
    province_name: str
    dataset_id: str
    variable: str
    start_date: date
    end_date: date


def create_investigation(request: InvestigationRequest) -> InvestigationRecord:
    """Valida e normaliza uma configuração sem executar análise científica."""
    if request.country_id != "angola":
        raise ValueError("Apenas o país Angola está disponível nesta etapa.")

    province = next((item for item in PROVINCES if item["id"] == request.province_id), None)
    if province is None:
        raise ValueError("Província não encontrada no catálogo de Angola.")

    dataset = next((item for item in DATASETS if item["id"] == request.dataset_id), None)
    if dataset is None:
        raise ValueError("Variável ambiental não encontrada no catálogo.")

    if request.start_date >= request.end_date:
        raise ValueError("A data inicial deve ser anterior à data final.")

    return InvestigationRecord(
        id=f"inv-{uuid4().hex[:12]}",
        status="configured",
        analysis_status="not_started",
        country_id=request.country_id,
        province_id=request.province_id,
        province_name=province["name"],
        dataset_id=request.dataset_id,
        variable=dataset["variable"],
        start_date=request.start_date,
        end_date=request.end_date,
    )
