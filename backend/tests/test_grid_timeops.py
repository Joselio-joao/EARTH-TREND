import unittest

import numpy as np

from app.analysis import grid, timeops


class Periods(unittest.TestCase):
    def test_bounds(self):
        self.assertEqual(timeops.parse_bound("2015", False), (2015, 1))
        self.assertEqual(timeops.parse_bound("2015", True), (2015, 12))
        self.assertEqual(timeops.parse_bound("2015-03", True), (2015, 3))
        self.assertEqual(timeops.parse_bound("2015-03-17", False), (2015, 3))
        for bad in ("15", "2015-13", "abc", "2015-00", "1800"):
            with self.assertRaises(ValueError):
                timeops.parse_bound(bad, False)

    def test_period_order_and_length(self):
        self.assertEqual(timeops.parse_period("2015", "2025"), ((2015, 1), (2025, 12)))
        with self.assertRaises(ValueError):
            timeops.parse_period("2025", "2015")
        self.assertEqual(timeops.months_between((2015, 1), (2015, 12)), 12)
        self.assertEqual(timeops.months_between((2014, 12), (2015, 1)), 2)

    def test_season_months(self):
        self.assertEqual(timeops.validate_season_months([12, 1, 2]), (12, 1, 2))
        self.assertEqual(timeops.season_label((12, 1, 2)), "DJF")
        self.assertEqual(timeops.season_label((10, 11, 12, 1, 2, 3, 4)), "10-04")
        for bad in ([], [1, 3], [13], list(range(1, 13)), [1, 1]):
            with self.assertRaises(ValueError):
                timeops.validate_season_months(bad)


class Windows(unittest.TestCase):
    ym = [(2014 + (11 + i) // 12, (11 + i) % 12 + 1) for i in range(25)]   # 2014-12 .. 2016-12

    def test_annual_windows_keep_complete_years_only(self):
        values = np.ones(25)
        labels, out, dropped = timeops.aggregate_windows(self.ym, values, tuple(range(1, 13)), "sum")
        self.assertEqual((labels, dropped), ([2015, 2016], [2014]))
        self.assertTrue(np.allclose(out, 12.0))

    def test_cube_shape_is_kept(self):
        labels, out, _ = timeops.aggregate_windows(self.ym, np.ones((25, 3, 2)), tuple(range(1, 13)), "mean")
        self.assertEqual(out.shape, (2, 3, 2))
        self.assertTrue(np.allclose(out, 1.0))

    def test_season_that_crosses_the_new_year(self):
        values = np.arange(1.0, 26.0)            # dez 2014 = 1, jan 2015 = 2, fev 2015 = 3 ...
        labels, out, dropped = timeops.aggregate_windows(self.ym, values, (12, 1, 2), "sum")
        self.assertEqual((labels, dropped), ([2015, 2016], [2017]))
        self.assertEqual(out[0], 1 + 2 + 3)

    def test_a_missing_month_drops_the_whole_year(self):
        ym = [x for x in self.ym if x != (2015, 6)]
        labels, _, dropped = timeops.aggregate_windows(ym, np.ones(len(ym)), tuple(range(1, 13)), "sum")
        self.assertEqual(labels, [2016])
        self.assertIn(2015, dropped)

    def test_nan_month_makes_the_window_nan_not_zero(self):
        values = np.ones(25)
        values[8] = np.nan                       # um mês de 2015
        _, out, _ = timeops.aggregate_windows(self.ym, values, tuple(range(1, 13)), "sum")
        self.assertTrue(np.isnan(out[0]) and out[1] == 12.0)


class Units(unittest.TestCase):
    def test_rate_factors(self):
        self.assertEqual(timeops.rate_per_day_factor("mm/hr"), 24.0)
        self.assertEqual(timeops.rate_per_day_factor("mm hr-1"), 24.0)
        self.assertEqual(timeops.rate_per_day_factor("mm/day"), 1.0)
        self.assertEqual(timeops.rate_per_day_factor("kg m-2 s-1"), 86400.0)
        self.assertIsNone(timeops.rate_per_day_factor("mm"))
        self.assertIsNone(timeops.rate_per_day_factor("degC"))
        self.assertTrue(timeops.unit_matches("MM/Day", ["mm/day", "mm/hr"]))
        self.assertFalse(timeops.unit_matches("mm/month", ["mm/day"]))

    def test_rate_becomes_a_monthly_total_using_the_real_month_length(self):
        ym = [(2021, 1), (2020, 2), (2021, 2)]
        day = timeops.convert_rate_to_totals(np.ones(3), ym, 1.0)
        self.assertTrue(np.allclose(day, [31, 29, 28]))
        hour = timeops.convert_rate_to_totals(np.full(3, 0.1), ym, 24.0)
        self.assertAlmostEqual(hour[0], 0.1 * 24 * 31)

    def test_conversion_keeps_cube_shape_and_can_run_in_place(self):
        cube = np.ones((2, 2, 2))
        out = timeops.convert_rate_to_totals(cube, [(2021, 1), (2021, 2)], 1.0)
        self.assertEqual(out.shape, (2, 2, 2))
        self.assertTrue(np.all(cube == 1.0))
        timeops.convert_rate_to_totals(cube, [(2021, 1), (2021, 2)], 1.0, inplace=True)
        self.assertTrue(np.all(cube[0] == 31.0) and np.all(cube[1] == 28.0))


class Grid(unittest.TestCase):
    def test_weights_follow_cos_latitude(self):
        mean, n = grid.area_weighted_mean(np.array([[[10.0], [20.0]]]), [0.0, 60.0])
        self.assertAlmostEqual(mean[0], (10 * 1.0 + 20 * 0.5) / 1.5)
        self.assertEqual(n[0], 2)

    def test_nan_cells_are_left_out_not_counted_as_zero(self):
        mean, n = grid.area_weighted_mean(np.array([[[np.nan], [20.0]]]), [0.0, 0.0])
        self.assertEqual((mean[0], n[0]), (20.0, 1))
        mean, n = grid.area_weighted_mean(np.array([[[np.nan], [np.nan]]]), [0.0, 0.0])
        self.assertTrue(np.isnan(mean[0]) and n[0] == 0)

    def test_mask_limits_the_region(self):
        mask = np.array([[True], [False]])
        mean, _ = grid.area_weighted_mean(np.array([[[10.0], [99.0]]]), [0.0, 0.0], mask)
        self.assertEqual(mean[0], 10.0)

    def test_bbox_mask(self):
        m = grid.bbox_mask([0, 1, 2, 3], [0, 1, 2], {"lat_min": 1, "lat_max": 2, "lon_min": 1, "lon_max": 2})
        self.assertEqual(int(m.sum()), 4)

    def test_polygon_with_a_hole(self):
        outer = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
        hole = [(1, 1), (3, 1), (3, 3), (1, 3), (1, 1)]
        centres = [0.5, 1.5, 2.5, 3.5, 4.5]
        m = grid.polygon_mask(centres, centres, [outer, hole])
        expected = np.zeros((5, 5), dtype=bool)
        expected[:4, :4] = True
        expected[1:3, 1:3] = False
        self.assertTrue(np.array_equal(m, expected))

    def test_geojson_rings_and_bbox(self):
        gj = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": [
                [[[10, -5], [12, -5], [12, -3], [10, -5]]],
                [[[20, -9], [22, -9], [22, -8], [20, -9]]]]}}]}
        rings = grid.rings_from_geojson(gj)
        self.assertEqual(len(rings), 2)
        self.assertEqual(grid.rings_bbox(rings), {"lat_min": -9.0, "lat_max": -3.0, "lon_min": 10.0, "lon_max": 22.0})

    def test_time_mean_ignores_nan(self):
        v = np.array([[[1.0, np.nan]], [[3.0, np.nan]]])
        m = grid.time_mean(v)
        self.assertEqual(m[0, 0], 2.0)
        self.assertTrue(np.isnan(m[0, 1]))

    def test_coarsen_averages_blocks_and_positions(self):
        f = np.arange(16.0).reshape(4, 4)
        out, la, lo = grid.coarsen(f, [0, 1, 2, 3], [10, 11, 12, 13], max_cells=2)
        self.assertEqual(out.shape, (2, 2))
        self.assertAlmostEqual(out[0, 0], (0 + 1 + 4 + 5) / 4.0)
        self.assertTrue(np.allclose(la, [0.5, 2.5]) and np.allclose(lo, [10.5, 12.5]))
        small, _, _ = grid.coarsen(f, [0, 1, 2, 3], [10, 11, 12, 13], max_cells=40)
        self.assertTrue(np.array_equal(small, f))

    def test_map_payload(self):
        f = np.array([[1.0, np.nan], [3.0, 5.0]])
        m = grid.make_map(f, [0.0, 1.0], [10.0, 11.0], "mm/ano", "média")
        self.assertEqual((m["min"], m["max"]), (1.0, 5.0))
        self.assertEqual(m["cell_size_deg"], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
