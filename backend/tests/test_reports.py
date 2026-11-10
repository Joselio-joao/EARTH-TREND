from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_report_generates_html_from_result() -> None:
    analysis = client.post(
        "/analyze",
        json={
            "investigation_id": "inv-report-001",
            "data_origin": "synthetic_test",
            "unit": "mm/ano",
            "observations": [
                {"date": "2000-01-01", "value": 10},
                {"date": "2001-01-01", "value": 12},
                {"date": "2002-01-01", "value": 14},
            ],
        },
    )
    result_id = analysis.json()["result_id"]

    response = client.get(f"/report/{result_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Relatório de investigação ambiental" in response.text
    assert "inv-report-001" in response.text
    assert "Dados sintéticos de teste" in response.text
    assert "não demonstram causalidade" in response.text


def test_report_unknown_result_returns_404() -> None:
    response = client.get("/report/res-unknown")

    assert response.status_code == 404
