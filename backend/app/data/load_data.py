from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import xarray as xr

from app.analysis.trend_analysis import Observation


@dataclass(frozen=True)
class LoadedSeries:
    observations: list[Observation]
    source_format: str
    source_path: str
    rows_read: int
    rows_dropped: int
    missing_values_removed: int


def _build_series(frame: pd.DataFrame, source_format: str, source_path: str) -> LoadedSeries:
    rows_read = len(frame)
    if "date" not in frame.columns or "value" not in frame.columns:
        raise ValueError("A série normalizada deve conter as colunas date e value.")

    dates = pd.to_datetime(frame["date"], errors="coerce", utc=True)
    values = pd.to_numeric(frame["value"], errors="coerce")
    valid = dates.notna() & values.notna()
    clean = pd.DataFrame({"date": dates[valid].dt.date, "value": values[valid].astype(float)})
    missing_values_removed = rows_read - len(clean)
    if clean.empty:
        raise ValueError("Não existem observações válidas depois de remover datas ou valores ausentes.")

    # Se houver mais do que uma observação no mesmo dia, agrega por média.
    clean = clean.groupby("date", as_index=False)["value"].mean().sort_values("date")
    observations = [
        Observation(date=row.date, value=float(row.value))
        for row in clean.itertuples(index=False)
    ]
    return LoadedSeries(
        observations=observations,
        source_format=source_format,
        source_path=source_path,
        rows_read=rows_read,
        rows_dropped=rows_read - len(clean),
        missing_values_removed=missing_values_removed,
    )


def load_csv_timeseries(
    path: str | Path,
    date_column: str = "date",
    value_column: str = "value",
) -> LoadedSeries:
    """Carrega uma série CSV e normaliza-a para Observation."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Ficheiro não encontrado: {csv_path}")
    frame = pd.read_csv(csv_path)
    if date_column not in frame.columns or value_column not in frame.columns:
        raise ValueError(f"O CSV deve conter as colunas '{date_column}' e '{value_column}'.")
    normalized = frame[[date_column, value_column]].rename(
        columns={date_column: "date", value_column: "value"}
    )
    return _build_series(normalized, "csv", str(csv_path))


def load_netcdf_timeseries(
    path: str | Path,
    variable_name: str,
    time_dimension: str = "time",
) -> LoadedSeries:
    """Carrega um NetCDF; calcula a média das dimensões espaciais."""
    netcdf_path = Path(path)
    if not netcdf_path.exists():
        raise FileNotFoundError(f"Ficheiro não encontrado: {netcdf_path}")

    with xr.open_dataset(netcdf_path) as dataset:
        if variable_name not in dataset.data_vars:
            raise ValueError(f"Variável '{variable_name}' não encontrada no NetCDF.")
        if time_dimension not in dataset.coords and time_dimension not in dataset.dims:
            raise ValueError(f"Dimensão temporal '{time_dimension}' não encontrada no NetCDF.")
        variable = dataset[variable_name]
        spatial_dimensions = [dimension for dimension in variable.dims if dimension != time_dimension]
        if spatial_dimensions:
            variable = variable.mean(dim=spatial_dimensions, skipna=True)
        frame = variable.to_dataframe(name="value").reset_index()
        frame = frame.rename(columns={time_dimension: "date"})[["date", "value"]]

    return _build_series(frame, "netcdf", str(netcdf_path))
