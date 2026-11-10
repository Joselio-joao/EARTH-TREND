from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_result_can_be_retrieved_and_listed() -> None:
    response = client.post(
        "/analyze",
        json={
            "investigation_id": "inv-results-001",
            "data_origin": "synthetic_test",
            "unit": "mm/ano",
            "observations": [
                {"date": "2000-01-01", "value": 10},
                {"date": "2001-01-01", "value": 12},
                {"date": "2002-01-01", "value": 14},
            ],
        },
    )

    assert response.status_code == 200
    result_id = response.json()["result_id"]

    retrieved = client.get(f"/results/{result_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["result_id"] == result_id
    assert retrieved.json()["payload"]["investigation_id"] == "inv-results-001"

    listed = client.get("/results?limit=5")
    assert listed.status_code == 200
    assert any(item["result_id"] == result_id for item in listed.json()["results"])


def test_unknown_result_returns_404() -> None:
    response = client.get("/results/res-does-not-exist")

    assert response.status_code == 404
