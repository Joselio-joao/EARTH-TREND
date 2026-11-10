from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from app.data.load_data import load_csv_timeseries, load_netcdf_timeseries


def test_load_csv_normalizes_dates_and_removes_missing_values(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "date": ["2000-01-01", "2001-01-01", "2002-01-01", "invalid"],
            "rainfall": [10, np.nan, 14, 20],
        }
    ).to_csv(csv_path, index=False)

    loaded = load_csv_timeseries(csv_path, value_column="rainfall")

    assert loaded.source_format == "csv"
    assert len(loaded.observations) == 2
    assert loaded.observations[0].value == 10.0
    assert loaded.observations[1].value == 14.0
    assert loaded.missing_values_removed == 2


def test_load_netcdf_aggregates_spatial_dimensions(tmp_path: Path) -> None:
    netcdf_path = tmp_path / "sample.nc"
    dataset = xr.Dataset(
        {
            "precipitation": (
                ("time", "lat", "lon"),
                [
                    [[10.0, 12.0], [14.0, 16.0]],
                    [[20.0, 22.0], [24.0, 26.0]],
                ],
            )
        },
        coords={
            "time": pd.date_range("2000-01-01", periods=2, freq="YS"),
            "lat": [-9.0, -10.0],
            "lon": [13.0, 14.0],
        },
    )
    dataset.to_netcdf(netcdf_path)

    loaded = load_netcdf_timeseries(netcdf_path, "precipitation")

    assert loaded.source_format == "netcdf"
    assert len(loaded.observations) == 2
    assert loaded.observations[0].value == 13.0
    assert loaded.observations[1].value == 23.0
