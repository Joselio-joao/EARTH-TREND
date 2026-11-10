from fastapi import FastAPI, HTTPException

from app.datasets import DATASETS, DatasetRecord
from app.regions import ANGOLA, OFFICIAL_SOURCE, PROVINCES, CountryRecord, ProvinceRecord
from app.investigations import InvestigationRecord, InvestigationRequest, create_investigation


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
