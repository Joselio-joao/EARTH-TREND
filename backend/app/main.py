from fastapi import FastAPI


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
