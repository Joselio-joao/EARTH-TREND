from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from tempfile import NamedTemporaryFile
from pathlib import Path

from app.datasets import DATASETS, DatasetRecord
from app.regions import ANGOLA, OFFICIAL_SOURCE, PROVINCES, CountryRecord, ProvinceRecord
from app.investigations import InvestigationRecord, InvestigationRequest, create_investigation
from app.analysis.models import AnalyzeRequest, AnalyzeResponse
from app.analysis.trend_analysis import Observation, analyze_trend
from app.data.sources import SCIENTIFIC_SOURCES, ScientificSource
from app.data.validate_data import validate_netcdf
from app.data.load_data import load_netcdf_timeseries


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


@app.get("/data-sources", tags=["data"])
def data_sources() -> dict[str, list[ScientificSource]]:
    """Lista fontes científicas registadas e o estado da sua integração."""
    return {"sources": SCIENTIFIC_SOURCES}


class DataValidationResponse(BaseModel):
    valid: bool
    filename: str
    variable: str
    dimensions: list[str]
    time_dimension: str
    units: str | None
    latitude_resolution: float | None
    longitude_resolution: float | None
    rows: int
    missing_values: int
    warnings: list[str]


class ScientificAnalyzeResponse(AnalyzeResponse):
    filename: str
    variable: str
    source_format: str
    rows_read: int
    rows_dropped: int
    missing_values_removed: int
    validation_warnings: list[str]


@app.post("/data/validate", response_model=DataValidationResponse, tags=["data"])
async def validate_data_file(
    file: UploadFile = File(...),
    variable_name: str = Query(..., min_length=1),
) -> DataValidationResponse:
    """Valida metadados de um NetCDF enviado sem guardar o ficheiro permanentemente."""
    if not file.filename or not file.filename.lower().endswith((".nc", ".nc4", ".netcdf")):
        raise HTTPException(status_code=415, detail="Envie um ficheiro NetCDF (.nc, .nc4 ou .netcdf).")

    temporary_path: str | None = None
    try:
        with NamedTemporaryFile(suffix=".nc", delete=False) as temporary:
            temporary.write(await file.read())
            temporary_path = temporary.name
        result = validate_netcdf(temporary_path, variable_name, file.filename)
        return DataValidationResponse(**result.__dict__)
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


@app.post("/data/analyze", response_model=ScientificAnalyzeResponse, tags=["data", "analysis"])
async def analyze_scientific_file(
    investigation_id: str = Query(..., min_length=1),
    variable_name: str = Query(..., min_length=1),
    file: UploadFile = File(...),
) -> ScientificAnalyzeResponse:
    """Valida, carrega e analisa um NetCDF científico sem o guardar permanentemente."""
    if not file.filename or not file.filename.lower().endswith((".nc", ".nc4", ".netcdf")):
        raise HTTPException(status_code=415, detail="Envie um ficheiro NetCDF (.nc, .nc4 ou .netcdf).")

    temporary_path: str | None = None
    try:
        with NamedTemporaryFile(suffix=".nc", delete=False) as temporary:
            temporary.write(await file.read())
            temporary_path = temporary.name
        validation = validate_netcdf(temporary_path, variable_name, file.filename)
        loaded = load_netcdf_timeseries(
            temporary_path,
            variable_name,
            time_dimension=validation.time_dimension,
        )
        if len(loaded.observations) < 3:
            raise ValueError("O ficheiro precisa de pelo menos 3 observações temporais válidas.")
        result = analyze_trend(loaded.observations)
        return ScientificAnalyzeResponse(
            investigation_id=investigation_id,
            data_origin="scientific_dataset",
            unit=validation.units or "unidade não declarada",
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
                "A série representa a média das dimensões espaciais do ficheiro.",
                "Confirmar escala, fator de conversão e indicadores de qualidade no produto original.",
            ],
            filename=file.filename,
            variable=variable_name,
            source_format=loaded.source_format,
            rows_read=loaded.rows_read,
            rows_dropped=loaded.rows_dropped,
            missing_values_removed=loaded.missing_values_removed,
            validation_warnings=validation.warnings,
        )
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


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
