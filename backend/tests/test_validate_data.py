from pathlib import Path

import pandas as pd
import xarray as xr
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _create_netcdf(path: Path) -> None:
    dataset = xr.Dataset(
        {"precipitationCal": (("time", "lat", "lon"), [[[1.0, 2.0]], [[3.0, 4.0]]])},
        coords={
            "time": pd.date_range("2000-01-01", periods=2, freq="YS"),
            "lat": [-9.0],
            "lon": [13.0, 13.1],
        },
    )
    dataset["precipitationCal"].attrs["units"] = "mm/hr"
    dataset.to_netcdf(path)


def test_validate_netcdf_returns_metadata(tmp_path: Path) -> None:
    path = tmp_path / "imerg-sample.nc"
    _create_netcdf(path)

    with path.open("rb") as file:
        response = client.post(
            "/data/validate?variable_name=precipitationCal",
            files={"file": ("imerg-sample.nc", file, "application/x-netcdf")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["variable"] == "precipitationCal"
    assert payload["units"] == "mm/hr"
    assert payload["time_dimension"] == "time"
    assert payload["longitude_resolution"] == 0.1


def test_validate_data_rejects_non_netcdf() -> None:
    response = client.post(
        "/data/validate?variable_name=precipitationCal",
        files={"file": ("sample.csv", b"date,value\n2000-01-01,1\n", "text/csv")},
    )

    assert response.status_code == 415
