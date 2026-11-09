from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_regions_returns_angola_and_21_provinces() -> None:
    response = client.get("/regions")

    assert response.status_code == 200
    payload = response.json()
    assert payload["country"] == {
        "id": "angola",
        "name": "Angola",
        "code": "AGO",
        "capital": "Luanda",
        "province_count": 21,
    }
    assert len(payload["provinces"]) == 21
    assert payload["source"] == "https://governo.gov.ao/angola/provincias"


def test_regions_include_recent_provincial_names() -> None:
    response = client.get("/regions")
    names = {province["name"] for province in response.json()["provinces"]}

    assert {"Cuando", "Cubango", "Icolo e Bengo", "Moxico Leste"}.issubset(names)
    assert "Luanda" in names
    assert "Cabinda" in names
