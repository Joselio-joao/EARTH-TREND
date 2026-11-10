from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_investigation_returns_normalized_configuration() -> None:
    response = client.post(
        "/investigations",
        json={
            "province_id": "luanda",
            "dataset_id": "gpm-imerg",
            "start_date": "2001-01-01",
            "end_date": "2020-12-31",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"].startswith("inv-")
    assert payload["status"] == "configured"
    assert payload["analysis_status"] == "not_started"
    assert payload["province_name"] == "Luanda"
    assert payload["variable"] == "Precipitação"


def test_create_investigation_rejects_unknown_province() -> None:
    response = client.post(
        "/investigations",
        json={
            "province_id": "unknown",
            "dataset_id": "gpm-imerg",
            "start_date": "2001-01-01",
            "end_date": "2020-12-31",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Província não encontrada no catálogo de Angola."


def test_create_investigation_rejects_invalid_period() -> None:
    response = client.post(
        "/investigations",
        json={
            "province_id": "huambo",
            "dataset_id": "modis-forest-cover",
            "start_date": "2020-12-31",
            "end_date": "2020-01-01",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "A data inicial deve ser anterior à data final."
