from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xarray as xr


@dataclass(frozen=True)
class NetCDFValidation:
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


def _coordinate_resolution(values: object) -> float | None:
    try:
        numeric = [float(value) for value in values]  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if len(numeric) < 2:
        return None
    differences = [abs(numeric[index + 1] - numeric[index]) for index in range(len(numeric) - 1)]
    return round(sum(differences) / len(differences), 6)


def validate_netcdf(path: str | Path, variable_name: str, filename: str) -> NetCDFValidation:
    """Inspeciona um NetCDF sem o transformar em resultado científico."""
    with xr.open_dataset(path, decode_times=True) as dataset:
        if variable_name not in dataset.data_vars:
            raise ValueError(f"Variável '{variable_name}' não encontrada no ficheiro.")
        variable = dataset[variable_name]
        time_dimension = next(
            (dimension for dimension in variable.dims if dimension.lower() in {"time", "date", "datetime"}),
            "",
        )
        if not time_dimension:
            raise ValueError("O ficheiro não apresenta uma dimensão temporal reconhecida.")

        lat_name = next((name for name in ("lat", "latitude") if name in dataset.coords), None)
        lon_name = next((name for name in ("lon", "longitude") if name in dataset.coords), None)
        units = variable.attrs.get("units")
        missing_values = int(variable.isnull().sum().item())
        warnings: list[str] = []
        if not units:
            warnings.append("A variável não declara unidades; confirmar no produto original.")
        if missing_values:
            warnings.append(f"Foram encontrados {missing_values} valores ausentes na variável.")
        warnings.append("Confirmar escala, fator de conversão e indicador de qualidade no produto NASA.")

        return NetCDFValidation(
            valid=True,
            filename=filename,
            variable=variable_name,
            dimensions=list(variable.dims),
            time_dimension=time_dimension,
            units=str(units) if units is not None else None,
            latitude_resolution=_coordinate_resolution(dataset[lat_name].values) if lat_name else None,
            longitude_resolution=_coordinate_resolution(dataset[lon_name].values) if lon_name else None,
            rows=int(variable.sizes[time_dimension]),
            missing_values=missing_values,
            warnings=warnings,
        )
