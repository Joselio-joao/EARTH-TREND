from pathlib import Path

import pandas as pd
import xarray as xr
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_scientific_netcdf_is_loaded_and_analyzed(tmp_path: Path) -> None:
    path = tmp_path / "scientific-sample.nc"
    values = [10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
    dataset = xr.Dataset(
        {"precipitationCal": (("time", "lat", "lon"), [[[value, value + 1]] for value in values])},
        coords={
            "time": pd.date_range("2000-01-01", periods=len(values), freq="YS"),
            "lat": [-9.0],
            "lon": [13.0, 13.1],
        },
    )
    dataset["precipitationCal"].attrs["units"] = "mm/hr"
    dataset.to_netcdf(path)

    with path.open("rb") as file:
        response = client.post(
            "/data/analyze?investigation_id=inv-real-001&variable_name=precipitationCal",
            files={"file": ("scientific-sample.nc", file, "application/x-netcdf")},
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["data_origin"] == "scientific_dataset"
    assert payload["source_format"] == "netcdf"
    assert payload["unit"] == "mm/hr"
    assert payload["n_observations"] == 6
    assert payload["direction"] == "crescente"
    assert payload["statistically_significant"] is True
    assert payload["rows_dropped"] == 0


def test_scientific_netcdf_requires_enough_time_points(tmp_path: Path) -> None:
    path = tmp_path / "short.nc"
    dataset = xr.Dataset(
        {"precipitationCal": (("time", "lat", "lon"), [[[1.0]], [[2.0]]])},
        coords={"time": pd.date_range("2000-01-01", periods=2, freq="YS"), "lat": [-9.0], "lon": [13.0]},
    )
    dataset.to_netcdf(path)

    with path.open("rb") as file:
        response = client.post(
            "/data/analyze?investigation_id=inv-short&variable_name=precipitationCal",
            files={"file": ("short.nc", file, "application/x-netcdf")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "O ficheiro precisa de pelo menos 3 observações temporais válidas."
