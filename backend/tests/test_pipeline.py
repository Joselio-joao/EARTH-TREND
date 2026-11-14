import json
import unittest

import numpy as np

from app.analysis import pipeline
from app.data.containers import Series
from app.errors import ApiError
from tests.synth import DATASET, REGION, make_cube, make_req


def run(cube=None, region=None, **kw):
    return pipeline.run_analysis(DATASET, region or REGION, make_req(**kw), cube or make_cube(), min_years=10)


class AnnualTrend(unittest.TestCase):
    def test_known_series_gives_the_expected_trend(self):
        r = run()
        t = r["trend"]
        self.assertEqual((r["status"], t["direction"], t["significant"]), ("ok", "increasing", True))
        # +0,01 mm/dia por ano, ou seja, cerca de 3,65 mm/ano por ano
        self.assertAlmostEqual(t["magnitude"]["slope_per_year"], 3.65, delta=0.5)
        self.assertLess(t["mann_kendall"]["p_value"], 0.001)
        self.assertEqual((r["unit"], len(r["series"]["values"]), r["trend"]["n_observations"]), ("mm/ano", 20, 20))
        self.assertEqual((r["series"]["labels"][0], r["series"]["labels"][-1]), ("2005", "2024"))
        self.assertAlmostEqual(r["series"]["values"][0], 2.0 * 365, places=6)       # 2005 não é bissexto
        self.assertEqual((r["data_quality"]["cells_in_region"], r["data_quality"]["valid_fraction"]), (25, 1.0))
        self.assertFalse(r["period"]["clipped"])
        self.assertEqual(len(r["series"]["trend_line"]), 20)
        self.assertIn("aumento", r["interpretation"]["summary"])
        self.assertNotIn("limitations", r["trend"])

    def test_map_is_the_time_mean_of_each_cell(self):
        m = run()["map"]
        self.assertEqual((len(m["lats"]), len(m["lons"]), m["unit"]), (5, 5, "mm/ano"))
        self.assertTrue(700 < m["min"] <= m["max"] < 800)

    def test_optional_trend_map_contains_cell_statistics(self):
        r = run(include_trend_map=True)
        tm = r["trend_map"]
        self.assertEqual((len(tm["lats"]), len(tm["lons"])), (5, 5))
        self.assertEqual(tm["directions"][0][0], "increasing")
        self.assertTrue(tm["significant"][0][0])
        self.assertLess(tm["p_values"][0][0], 0.001)
        self.assertAlmostEqual(tm["slopes_per_year"][0][0], 3.65, delta=0.5)

    def test_trend_map_is_not_calculated_by_default(self):
        self.assertIsNone(run()["trend_map"])

    def test_every_payload_is_valid_json(self):
        json.dumps(run(), allow_nan=False)
        json.dumps(run(cube=make_cube(first_year=2015, last_year=2019), start="2015", end="2019"), allow_nan=False)

    def test_provenance_and_dataset_are_reported(self):
        r = run()
        self.assertEqual(r["dataset"]["doi"], "10.5067/GPM/IMERG/3B-MONTH/07")
        self.assertEqual(r["provenance"]["unit_in_data"], "mm/day")
        self.assertTrue(r["provenance"]["unit_declared_in_data"])
        self.assertEqual(r["provenance"]["files"][0]["name"], "SINTETICO-teste.nc")
        self.assertTrue(any("caixa" in w for w in r["warnings"]))               # região = caixa aproximada
        self.assertTrue(any("constelação" in x for x in r["limitations"]))      # limitação do produto

    def test_rate_per_hour_gives_the_same_answer(self):
        a = run()
        b = run(cube=make_cube(rate0=2.0 / 24, rate_slope=0.01 / 24, unit="mm/hr"))
        self.assertTrue(np.allclose(a["series"]["values"], b["series"]["values"], rtol=1e-9))
        self.assertAlmostEqual(a["trend"]["magnitude"]["slope_per_year"], b["trend"]["magnitude"]["slope_per_year"])


class Units(unittest.TestCase):
    def test_unknown_units_are_refused(self):
        for unit in ("mm", "mm/month", "degC"):
            with self.assertRaises(ApiError, msg=unit) as ctx:
                run(cube=make_cube(unit=unit))
            self.assertEqual(ctx.exception.code, "unit_mismatch")

    def test_missing_units_fall_back_to_the_registry_with_a_warning(self):
        r = run(cube=make_cube(unit=None))
        self.assertFalse(r["provenance"]["unit_declared_in_data"])
        self.assertTrue(any("não declaram unidades" in w for w in r["warnings"]))
        self.assertAlmostEqual(r["series"]["values"][0], 730.0)


class Scales(unittest.TestCase):
    def test_monthly_uses_the_seasonal_test(self):
        r = run(scale="monthly")
        self.assertEqual((r["unit"], r["trend"]["n_observations"], r["series"]["labels"][0]), ("mm/mês", 240, "2005-01"))
        self.assertIn("sazonal", r["trend"]["method"])
        self.assertEqual(r["trend"]["direction"], "increasing")
        self.assertAlmostEqual(r["series"]["values"][0], 2.0 * 31)

    def test_season_that_crosses_the_year_borrows_the_previous_december(self):
        cube = make_cube(first_year=2004, last_year=2024)
        r = run(cube=cube, scale="seasonal", season_months=(12, 1, 2), season_label="DJF", load_start=(2004, 1))
        self.assertEqual((r["unit"], r["scale_label"], len(r["series"]["labels"])), ("mm/época (DJF)", "sazonal (DJF)", 20))
        self.assertEqual(r["series"]["labels"][0], "2005")
        self.assertAlmostEqual(r["series"]["values"][0], 2.0 * 31 + 2.01 * 31 + 2.01 * 28, places=6)
        self.assertTrue(0.3 < r["trend"]["magnitude"]["slope_per_year"] < 1.5)

    def test_incomplete_years_are_dropped_and_reported(self):
        r = run(cube=make_cube(start_month=3))
        self.assertEqual(r["series"]["labels"][0], "2006")
        self.assertTrue(r["period"]["clipped"])
        self.assertEqual(r["data_quality"]["incomplete_windows_dropped"], [2005])
        self.assertTrue(any("Excluídos" in w for w in r["warnings"]))
        self.assertTrue(any("não está todo coberto" in w for w in r["warnings"]))

    def test_no_complete_year_is_an_error(self):
        cube = make_cube(first_year=2005, last_year=2005, start_month=3)
        with self.assertRaises(ApiError) as ctx:
            run(cube=cube, start="2005", end="2005")
        self.assertEqual(ctx.exception.code, "no_complete_windows")

    def test_period_outside_the_data_is_an_error(self):
        with self.assertRaises(ApiError) as ctx:
            run(start="2030", end="2031")
        self.assertEqual(ctx.exception.code, "no_data_in_period")
        self.assertIn("2005-01 a 2024-12", ctx.exception.message)


class Inconclusive(unittest.TestCase):
    def test_short_series_is_inconclusive_with_no_invented_numbers(self):
        r = run(cube=make_cube(first_year=2015, last_year=2019), start="2015", end="2019")
        self.assertEqual((r["status"], r["trend"]["direction"]), ("inconclusive", "inconclusive"))
        self.assertIsNone(r["trend"]["sen"])
        self.assertIsNone(r["trend"]["magnitude"])
        self.assertIsNone(r["series"]["trend_line"])
        self.assertTrue(r["interpretation"]["summary"].startswith("Não foi possível concluir"))


class Regions(unittest.TestCase):
    @staticmethod
    def two_zone_cube():
        cube = make_cube()
        cube.values[:, :, :2] = 1.0       # duas colunas secas
        cube.values[:, :, 2:] = 3.0       # três colunas húmidas (lon 16, 17, 18)
        return cube

    def test_polygon_limits_the_average_to_its_cells(self):
        ring = [(15.5, -12.5), (18.5, -12.5), (18.5, -7.5), (15.5, -7.5), (15.5, -12.5)]
        region = dict(REGION, rings=[ring], boundary="polygon", approximate=False,
                      bbox={"lat_min": -12.5, "lat_max": -7.5, "lon_min": 15.5, "lon_max": 18.5})
        r = run(cube=self.two_zone_cube(), region=region)
        self.assertEqual(r["region"]["cells"], 15)
        self.assertAlmostEqual(r["series"]["values"][0], 3.0 * 365)
        self.assertFalse(any("caixa" in w for w in r["warnings"]))
        self.assertTrue(all(v is None for row in r["map"]["values"] for v in row[:1]))   # fora do polígono

    def test_without_polygon_the_box_average_is_used(self):
        r = run(cube=self.two_zone_cube())
        self.assertAlmostEqual(r["series"]["values"][0], 2.2 * 365)
        self.assertEqual(r["region"]["cells"], 25)

    def test_a_region_with_no_cell_centres_is_an_error(self):
        ring = [(100, 0), (101, 0), (101, 1), (100, 1), (100, 0)]
        region = dict(REGION, rings=[ring], boundary="polygon", approximate=False,
                      bbox={"lat_min": 0, "lat_max": 1, "lon_min": 100, "lon_max": 101})
        with self.assertRaises(ApiError) as ctx:
            run(region=region)
        self.assertEqual(ctx.exception.code, "region_without_cells")

    def test_missing_cells_are_left_out_not_zeroed(self):
        cube = make_cube()
        cube.values[:, 0, 0] = np.nan
        r = run(cube=cube)
        self.assertEqual(r["data_quality"]["cells_used_mean"], 24.0)
        self.assertAlmostEqual(r["series"]["values"][0], 730.0)


class AlreadyAggregatedSeries(unittest.TestCase):
    def test_csv_style_series_has_no_map_and_no_cells(self):
        ym = [(y, m) for y in range(2005, 2025) for m in range(1, 13)]
        values = np.array([2.0 + 0.01 * (y - 2005) for y, _ in ym])
        src = Series(ym, values, "mm/day", [{"name": "angola.csv", "modified": "2026-11-01"}], {"source": "teste"}, 0)
        r = run(cube=src)
        self.assertEqual(r["trend"]["direction"], "increasing")
        self.assertIsNone(r["map"])
        self.assertIsNone(r["data_quality"]["cells_in_region"])
        self.assertAlmostEqual(r["series"]["values"][0], 730.0)
        json.dumps(r, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
