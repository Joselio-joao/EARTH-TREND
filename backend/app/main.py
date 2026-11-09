from fastapi import FastAPI

from app.datasets import DATASETS, DatasetRecord


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
