import json
import tempfile
import unittest
from pathlib import Path

from app.config import PACKAGE_DATA, Settings
from app.data.registry import Registry
from app.data.sources import FileLoader
from app.errors import ApiError
from app.service import Service
from app.storage import ResultStore
from tests.synth import make_cube

PAYLOAD = {"dataset_id": "gpm_imerg_monthly", "region_id": "angola", "start": "2005", "end": "2024",
           "scale": "annual", "question": "A precipitação está a mudar?"}


class FakeLoader:
    """Devolve sempre o cubo sintético e regista com que período foi chamado."""

    def __init__(self, factory=make_cube):
        self.factory, self.calls = factory, []

    def available(self, dataset):
        return {"grid_files": 1, "series_files": 0}

    def load(self, dataset, region, start, end):
        self.calls.append((region["id"], start, end))
        return self.factory()


class ServiceBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = Settings(data_dir=Path(self.tmp.name))
        self.registry = Registry.load(PACKAGE_DATA, self.settings.regions_dir)
        self.loader = FakeLoader()
        self.svc = Service(self.settings, self.registry, self.loader, ResultStore(self.settings.results_dir))

    def tearDown(self):
        self.tmp.cleanup()

    def fails(self, payload, status, code):
        with self.assertRaises(ApiError, msg=str(payload)) as ctx:
            self.svc.analyze(payload)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (status, code), ctx.exception.message)


class Flow(ServiceBase):
    def test_analyze_store_and_read_back(self):
        r = self.svc.analyze(PAYLOAD)
        self.assertRegex(r["id"], r"^[0-9a-f]{32}$")
        self.assertTrue(r["created_at"].endswith("Z"))
        self.assertEqual(r["trend"]["direction"], "increasing")
        self.assertEqual(r["links"]["self"], "/results/" + r["id"])
        self.assertEqual(self.svc.get_result(r["id"]), json.loads(json.dumps(r)))
        self.assertEqual(self.svc.list_results()[0]["id"], r["id"])
        self.assertEqual(self.svc.get_map(r["id"])["unit"], "mm/ano")
        self.assertEqual(self.loader.calls[-1], ("angola", (2005, 1), (2024, 12)))

    def test_report_formats_and_csv(self):
        rid = self.svc.analyze(PAYLOAD)["id"]
        page, ctype = self.svc.report(rid, "html")
        self.assertTrue(ctype.startswith("text/html"))
        for needle in ("<svg", "Mann-Kendall", "Limitações", "10.5067/GPM/IMERG/3B-MONTH/07", "Aumento",
                       "A precipitação está a mudar?", "SINTETICO-teste.nc"):
            self.assertIn(needle, page)
        md, ctype = self.svc.report(rid, "md")
        self.assertTrue(ctype.startswith("text/markdown"))
        self.assertIn("## Limitações", md)
        self.assertIn("Valor-p", md)
        csv_text, name = self.svc.series_csv(rid)
        lines = csv_text.strip().split("\n")
        self.assertEqual(lines[0], "periodo,valor,unidade,linha_de_tendencia")
        self.assertEqual(len(lines), 21)
        first = lines[1].split(",")
        self.assertEqual((first[0], first[2]), ("2005", "mm/ano"))
        self.assertAlmostEqual(float(first[1]), 730.0, places=6)
        self.assertTrue(name.startswith("earthtrend-") and name.endswith(".csv"))
        with self.assertRaises(ApiError):
            self.svc.report(rid, "pdf")

    def test_user_text_cannot_inject_html(self):
        rid = self.svc.analyze(dict(PAYLOAD, question="<script>alert(1)</script>"))["id"]
        page, _ = self.svc.report(rid, "html")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_custom_box(self):
        p = {k: v for k, v in PAYLOAD.items() if k != "region_id"}
        r = self.svc.analyze(dict(p, bbox={"lat_min": -11.5, "lat_max": -8.5, "lon_min": 14.5, "lon_max": 17.5}))
        self.assertEqual((r["region"]["id"], r["region"]["cells"], r["region"]["boundary"]), ("custom", 9, "custom"))
        self.assertIsNone(r["request"]["region_id"])

    def test_seasonal_wrap_asks_the_loader_for_the_previous_year(self):
        self.loader.factory = lambda: make_cube(first_year=2004)
        r = self.svc.analyze(dict(PAYLOAD, scale="seasonal", season="djf"))
        self.assertEqual(self.loader.calls[-1][1], (2004, 1))
        self.assertEqual((r["request"]["season"], r["unit"]), ("DJF", "mm/época (DJF)"))
        self.svc.analyze(dict(PAYLOAD, scale="seasonal", season_months=[3, 4, 5]))
        self.assertEqual(self.loader.calls[-1][1], (2005, 1))

    def test_native_scale_is_the_datasets_own(self):
        self.assertEqual(self.svc.analyze(dict(PAYLOAD, scale="native"))["scale"], "monthly")

    def test_listings(self):
        by_id = {d["id"]: d for d in self.svc.list_datasets()}
        self.assertTrue(by_id["gpm_imerg_monthly"]["ready"])
        self.assertEqual(by_id["gpm_imerg_monthly"]["files"], {"grid_files": 1, "series_files": 0})
        self.assertEqual((by_id["gistemp"]["ready"], by_id["gistemp"]["status"]), (False, "planned"))
        regions = {r["id"]: r for r in self.svc.list_regions()}
        self.assertTrue(regions["angola"]["ready"] and not regions["luanda"]["ready"])
        self.assertEqual(self.svc.health()["status"], "ok")


class Validation(ServiceBase):
    def test_bad_requests_are_422_with_a_code(self):
        no_region = {k: v for k, v in PAYLOAD.items() if k != "region_id"}
        box = {"lat_min": -11, "lat_max": -9, "lon_min": 14, "lon_max": 16}
        self.fails(no_region, 422, "invalid_request")
        self.fails(dict(PAYLOAD, bbox=box), 422, "invalid_request")
        self.fails(dict(no_region, bbox=dict(box, lat_min=-5)), 422, "invalid_bbox")
        self.fails(dict(no_region, bbox={"lat_min": 1}), 422, "invalid_bbox")
        self.fails(dict(PAYLOAD, start="2025", end="2015"), 422, "invalid_period")
        self.fails(dict(PAYLOAD, start="ontem"), 422, "invalid_period")
        self.fails({k: v for k, v in PAYLOAD.items() if k != "end"}, 422, "invalid_period")
        self.fails(dict(PAYLOAD, scale="diaria"), 422, "invalid_scale")
        self.fails(dict(PAYLOAD, scale="seasonal"), 422, "invalid_season")
        self.fails(dict(PAYLOAD, scale="seasonal", season="XYZ"), 422, "invalid_season")
        self.fails(dict(PAYLOAD, scale="seasonal", season_months=[1, 3]), 422, "invalid_season")
        self.fails(dict(PAYLOAD, alpha=0.9), 422, "invalid_alpha")
        self.fails(dict(PAYLOAD, alpha="x"), 422, "invalid_alpha")
        self.fails(dict(PAYLOAD, question="x" * 301), 422, "invalid_question")

    def test_unknown_or_unready_things(self):
        self.fails(dict(PAYLOAD, dataset_id="nope"), 404, "dataset_not_found")
        self.fails(dict(PAYLOAD, dataset_id="gistemp"), 422, "dataset_not_ready")
        self.fails(dict(PAYLOAD, region_id="atlantida"), 404, "region_not_found")
        self.fails(dict(PAYLOAD, region_id="Luanda, Angola"), 422, "region_needs_boundary")

    def test_oversized_requests_are_refused_before_loading_anything(self):
        self.fails(dict(PAYLOAD, region_id="global"), 422, "request_too_large")
        self.assertEqual(self.loader.calls, [])

    def test_busy_server_says_429_and_recovers(self):
        for _ in range(self.settings.max_concurrent):
            self.svc.slots.acquire()
        self.fails(PAYLOAD, 429, "busy")
        for _ in range(self.settings.max_concurrent):
            self.svc.slots.release()
        self.assertEqual(self.svc.analyze(PAYLOAD)["status"], "ok")

    def test_slot_is_released_when_the_analysis_fails(self):
        self.loader.factory = lambda: make_cube(unit="mm")
        for _ in range(self.settings.max_concurrent + 2):
            self.fails(PAYLOAD, 422, "unit_mismatch")

    def test_unknown_result_ids(self):
        for rid in ("0" * 32, "../../etc/passwd", "abc", "A" * 32, ""):
            with self.assertRaises(ApiError) as ctx:
                self.svc.get_result(rid)
            self.assertEqual(ctx.exception.status, 404)

    def test_no_data_on_the_server_is_a_409_not_invented_numbers(self):
        svc = Service(self.settings, self.registry, FileLoader(self.settings.raw_dir),
                      ResultStore(self.settings.results_dir))
        with self.assertRaises(ApiError) as ctx:
            svc.analyze(PAYLOAD)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (409, "data_unavailable"))
        self.assertFalse(svc.list_datasets()[0]["ready"])
        self.assertEqual(svc.list_results(), [])


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ResultStore(Path(self.tmp.name) / "results")

    def tearDown(self):
        self.tmp.cleanup()

    def test_id_rules(self):
        self.assertTrue(ResultStore.valid_id(ResultStore.new_id()))
        for bad in ("../x", "abc", "G" * 32, "a" * 31, ""):
            self.assertFalse(ResultStore.valid_id(bad))
            self.assertIsNone(self.store.load(bad))

    def test_roundtrip_listing_order_and_nan_refusal(self):
        a, b = ResultStore.new_id(), ResultStore.new_id()
        self.store.save({"id": a, "created_at": "1"})
        self.store.save({"id": b, "created_at": "2", "trend": {"direction": "no_trend"}})
        self.assertEqual(self.store.load(a)["created_at"], "1")
        self.assertEqual({x["id"] for x in self.store.list()}, {a, b})
        with self.assertRaises(ValueError):
            self.store.save({"id": ResultStore.new_id(), "x": float("nan")})
        self.assertEqual(list(self.store.dir.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
