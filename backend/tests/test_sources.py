from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_scientific_sources_register_imerg_metadata() -> None:
    response = client.get("/data-sources")

    assert response.status_code == 200
    sources = response.json()["sources"]
    imerg = next(item for item in sources if item["dataset_id"] == "gpm-imerg")

    assert imerg["run"] == "Final"
    assert "NetCDF" in imerg["format_options"]
    assert "0.1° × 0.1°" == imerg["spatial_resolution"]
    assert imerg["access_status"] == "metadata_registered_file_not_downloaded"
    assert "confirmada" in " ".join(imerg["notes"])
