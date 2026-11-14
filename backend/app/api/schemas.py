"""Formato dos pedidos da API (o FastAPI usa isto para validar e para gerar /docs)."""
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class BBox(BaseModel):
    lat_min: float = Field(..., description="Latitude mínima em graus (sul é negativo)")
    lat_max: float = Field(..., description="Latitude máxima")
    lon_min: float = Field(..., description="Longitude mínima em graus (oeste é negativo)")
    lon_max: float = Field(..., description="Longitude máxima")


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{
        "dataset_id": "gpm_imerg_monthly", "region_id": "angola", "start": "2015", "end": "2025",
        "scale": "annual", "question": "A precipitação anual em Angola está a mudar?"}]})

    dataset_id: str = Field("gpm_imerg_monthly", max_length=64, description="id de GET /datasets")
    region_id: Optional[str] = Field(None, max_length=64, description="id ou nome de GET /regions (ou use bbox)")
    bbox: Optional[BBox] = Field(None, description="Caixa personalizada, em alternativa a region_id")
    start: Union[str, int] = Field(..., description="AAAA, AAAA-MM ou AAAA-MM-DD")
    end: Union[str, int] = Field(..., description="AAAA, AAAA-MM ou AAAA-MM-DD")
    scale: str = Field("annual", max_length=10, description="monthly, seasonal, annual ou native")
    season: Optional[str] = Field(None, max_length=3, description="DJF, MAM, JJA ou SON (com scale=seasonal)")
    season_months: Optional[List[int]] = Field(None, max_length=11,
                                               description="Alternativa a season: meses consecutivos, ex.: [10,11,12,1,2,3,4]")
    alpha: float = Field(0.05, gt=0, lt=0.5, description="Nível de significância (e IC de 1-alpha)")
    question: Optional[str] = Field(None, max_length=300, description="Pergunta de investigação (aparece no relatório)")
    include_trend_map: bool = Field(False, description="Calcula a tendência estatística célula a célula para o mapa")
