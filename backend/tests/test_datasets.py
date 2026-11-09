from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_datasets_returns_supported_environmental_variables() -> None:
    response = client.get("/datasets")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["datasets"]) == 6

    variables = {item["variable"] for item in payload["datasets"]}
    assert variables == {
        "Precipitação",
        "Vegetação",
        "Temperatura",
        "Humidade do solo",
        "Armazenamento de água terrestre",
        "Cobertura florestal",
    }


def test_dataset_purposes_are_explicit() -> None:
    response = client.get("/datasets")
    by_variable = {item["variable"]: item for item in response.json()["datasets"]}

    assert by_variable["Humidade do solo"]["purpose"] == "Investigar secas e disponibilidade de água."
    assert by_variable["Armazenamento de água terrestre"]["purpose"] == "Identificar mudanças nos recursos hídricos."
    assert by_variable["Cobertura florestal"]["purpose"] == "Investigar transformação dos ecossistemas."
