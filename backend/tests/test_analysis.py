from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_analyze_detects_a_significant_increasing_synthetic_series() -> None:
    response = client.post(
        "/analyze",
        json={
            "investigation_id": "inv-test-001",
            "data_origin": "synthetic_test",
            "unit": "mm/ano",
            "observations": [
                {"date": "2000-01-01", "value": 10},
                {"date": "2001-01-01", "value": 12},
                {"date": "2002-01-01", "value": 14},
                {"date": "2003-01-01", "value": 16},
                {"date": "2004-01-01", "value": 18},
                {"date": "2005-01-01", "value": 20},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_origin"] == "synthetic_test"
    assert payload["direction"] == "crescente"
    assert payload["statistically_significant"] is True
    assert payload["sen_slope_per_year"] == 2.0


def test_analyze_rejects_too_few_observations() -> None:
    response = client.post(
        "/analyze",
        json={
            "investigation_id": "inv-test-002",
            "data_origin": "synthetic_test",
            "unit": "mm",
            "observations": [
                {"date": "2000-01-01", "value": 1},
                {"date": "2001-01-01", "value": 2},
            ],
        },
    )

    assert response.status_code == 422


def test_analyze_rejects_duplicate_dates() -> None:
    response = client.post(
        "/analyze",
        json={
            "investigation_id": "inv-test-003",
            "data_origin": "scientific_dataset",
            "unit": "mm",
            "observations": [
                {"date": "2000-01-01", "value": 1},
                {"date": "2000-01-01", "value": 2},
                {"date": "2001-01-01", "value": 3},
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "As observações não podem repetir a mesma data."
