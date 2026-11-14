"""Testes HTTP com o TestClient do FastAPI. Só correm se o fastapi e o httpx estiverem instalados."""
import tempfile
import unittest
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    HAVE_API = True
except Exception:          # fastapi ou httpx em falta
    HAVE_API = False

from app.config import Settings
from tests.test_service import PAYLOAD, FakeLoader


@unittest.skipUnless(HAVE_API, "fastapi e httpx não estão instalados (pip install -r requirements-dev.txt)")
class Api(unittest.TestCase):
    def setUp(self):
        from app.main import create_app
        self.create_app = create_app
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(data_dir=Path(self.tmp.name))
        self.client = TestClient(create_app(self.settings, loader=FakeLoader()))

    def tearDown(self):
        self.tmp.cleanup()

    def test_catalogue_endpoints(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        datasets = {d["id"]: d for d in self.client.get("/datasets").json()["datasets"]}
        self.assertTrue(datasets["gpm_imerg_monthly"]["ready"])
        regions = {r["id"]: r for r in self.client.get("/regions").json()["regions"]}
        self.assertTrue(regions["angola"]["ready"])
        self.assertEqual(self.client.get("/").json()["docs"], "/docs")

    def test_full_flow(self):
        r = self.client.post("/analyze", json=PAYLOAD)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        rid = body["id"]
        self.assertEqual(body["trend"]["direction"], "increasing")
        self.assertEqual(self.client.get("/results/" + rid).json()["id"], rid)
        self.assertEqual(self.client.get("/results/%s/map" % rid).json()["unit"], "mm/ano")
        self.assertEqual(self.client.get("/results").json()["results"][0]["id"], rid)
        csv = self.client.get("/results/%s/series.csv" % rid)
        self.assertTrue(csv.headers["content-type"].startswith("text/csv"))
        self.assertIn("attachment", csv.headers["content-disposition"])
        html = self.client.get("/report/" + rid)
        self.assertTrue(html.headers["content-type"].startswith("text/html"))
        self.assertIn("<svg", html.text)
        self.assertIn("## Limitações", self.client.get("/report/%s?format=md" % rid).text)
        self.assertEqual(self.client.get("/report/%s?format=pdf" % rid).status_code, 422)

    def test_trend_map_flow(self):
        r = self.client.post("/analyze", json=dict(PAYLOAD, include_trend_map=True))
        self.assertEqual(r.status_code, 200, r.text)
        rid = r.json()["id"]
        trend_map = self.client.get("/results/%s/trend-map" % rid)
        self.assertEqual(trend_map.status_code, 200)
        self.assertEqual(trend_map.json()["directions"][0][0], "increasing")

    def test_trend_map_requires_explicit_request(self):
        r = self.client.post("/analyze", json=PAYLOAD)
        rid = r.json()["id"]
        self.assertEqual(self.client.get("/results/%s/trend-map" % rid).status_code, 404)

    def test_years_can_be_sent_as_numbers(self):
        self.assertEqual(self.client.post("/analyze", json=dict(PAYLOAD, start=2005, end=2024)).status_code, 200)

    def test_errors_have_a_json_body_with_a_code(self):
        r = self.client.post("/analyze", json=dict(PAYLOAD, region_id="atlantida"))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (404, "region_not_found"))
        r = self.client.post("/analyze", json=dict(PAYLOAD, bbox={"lat_min": -10, "lat_max": -9, "lon_min": 14, "lon_max": 15}))
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (422, "invalid_request"))
        self.assertEqual(self.client.post("/analyze", json={"region_id": "angola"}).status_code, 422)
        self.assertEqual(self.client.post("/analyze", json=dict(PAYLOAD, alpha=0.9)).status_code, 422)
        self.assertEqual(self.client.get("/results/" + "0" * 32).status_code, 404)
        self.assertEqual(self.client.get("/results/..%2F..%2Fetc%2Fpasswd").status_code, 404)

    def test_without_data_the_server_says_409(self):
        client = TestClient(self.create_app(self.settings))        # carregador real, pasta vazia
        r = client.post("/analyze", json=PAYLOAD)
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (409, "data_unavailable"))

    def test_cors_only_for_the_known_origins(self):
        ok = self.client.get("/health", headers={"Origin": "https://joselio-joao.github.io"})
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "https://joselio-joao.github.io")
        bad = self.client.get("/health", headers={"Origin": "https://evil.example"})
        self.assertNotIn("access-control-allow-origin", bad.headers)


if __name__ == "__main__":
    unittest.main()
