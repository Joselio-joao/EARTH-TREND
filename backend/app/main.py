from fastapi import FastAPI, HTTPException

from app.datasets import DATASETS, DatasetRecord
from app.regions import ANGOLA, OFFICIAL_SOURCE, PROVINCES, CountryRecord, ProvinceRecord
from app.investigations import InvestigationRecord, InvestigationRequest, create_investigation
from app.analysis.models import AnalyzeRequest, AnalyzeResponse
from app.analysis.trend_analysis import Observation, analyze_trend


API_VERSION = "0.1.0"

app = FastAPI(
    title="EarthTrend AI API",
    description="Backend científico para investigações ambientais da EarthTrend AI.",
    version=API_VERSION,
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Confirma que a API está disponível."""
    return {
        "status": "ok",
        "service": "earthtrend-api",
        "version": API_VERSION,
    }


@app.get("/datasets", tags=["catalog"])
def datasets() -> dict[str, list[DatasetRecord]]:
    """Lista as variáveis ambientais disponíveis ou planeadas."""
    return {"datasets": DATASETS}


@app.get("/regions", tags=["catalog"])
def regions() -> dict[str, CountryRecord | list[ProvinceRecord] | str]:
    """Lista Angola e as suas províncias para configurar uma investigação."""
    return {
        "country": ANGOLA,
        "provinces": PROVINCES,
        "source": OFFICIAL_SOURCE,
    }


@app.post("/investigations", response_model=InvestigationRecord, tags=["investigations"])
def investigations(request: InvestigationRequest) -> InvestigationRecord:
    """Valida e cria a configuração de uma investigação ambiental."""
    try:
        return create_investigation(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """Calcula uma tendência temporal a partir de observações fornecidas."""
    try:
        result = analyze_trend(
            [Observation(date=item.date, value=item.value) for item in request.observations]
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return AnalyzeResponse(
        investigation_id=request.investigation_id,
        data_origin=request.data_origin,
        unit=request.unit,
        n_observations=result.n_observations,
        slope_per_year=result.slope_per_year,
        sen_slope_per_year=result.sen_slope_per_year,
        r_squared=result.r_squared,
        mann_kendall_s=result.mann_kendall_s,
        mann_kendall_z=result.mann_kendall_z,
        p_value=result.p_value,
        direction=result.direction,
        statistically_significant=result.statistically_significant,
        limitations=[
            "Uma tendência estatística não demonstra causalidade.",
            "A interpretação depende da qualidade, cobertura e resolução dos dados.",
            "Dados synthetic_test são apenas para validação do algoritmo e não representam dados NASA.",
        ],
    )
