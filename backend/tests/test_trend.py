import math
import unittest
from collections import Counter

import numpy as np

from app.analysis import trend


def brute_mk(x):
    """Definição de livro, com ciclos, para comparar com a versão vetorizada."""
    n = len(x)
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            d = x[j] - x[i]
            s += int(d > 0) - int(d < 0)
    ties = sum(c * (c - 1) * (2 * c + 5) for c in Counter(x).values() if c > 1)
    return float(s), (n * (n - 1) * (2 * n + 5) - ties) / 18.0


class MannKendall(unittest.TestCase):
    def test_perfect_increase(self):
        s, var = trend.mk_statistic(list(range(1, 11)))
        self.assertEqual((s, var), (45.0, 125.0))
        z, p = trend.mk_z_p(s, var)
        self.assertAlmostEqual(z, 44 / math.sqrt(125))
        self.assertLess(p, 1e-4)

    def test_matches_textbook_definition_with_ties(self):
        rng = np.random.default_rng(7)
        for n in (5, 12, 30):
            x = rng.integers(0, 6, size=n).astype(float)
            s, var = trend.mk_statistic(x)
            bs, bv = brute_mk(list(x))
            self.assertEqual(s, bs)
            self.assertAlmostEqual(var, bv)

    def test_z_uses_continuity_correction_and_keeps_sign(self):
        self.assertAlmostEqual(trend.mk_z_p(10.0, 100.0)[0], 0.9)
        self.assertAlmostEqual(trend.mk_z_p(-10.0, 100.0)[0], -0.9)
        z, p = trend.mk_z_p(0.0, 100.0)
        self.assertEqual((z, p), (0.0, 1.0))
        self.assertTrue(math.isnan(trend.mk_z_p(5.0, 0.0)[1]))

    def test_type_one_error_rate_is_close_to_alpha(self):
        rng = np.random.default_rng(12345)
        t = np.arange(2000.0, 2020.0)
        hits = sum(trend.analyze_trend(t, rng.normal(size=20))["significant"] for _ in range(1500))
        self.assertTrue(0.03 <= hits / 1500.0 <= 0.07, hits / 1500.0)

    def test_power_with_a_clear_trend(self):
        rng = np.random.default_rng(99)
        t = np.arange(2000.0, 2020.0)
        hits = sum(trend.analyze_trend(t, 0.3 * (t - 2000) + rng.normal(size=20))["significant"]
                   for _ in range(300))
        self.assertGreater(hits / 300.0, 0.95)


class SenSlope(unittest.TestCase):
    def test_exact_line_gives_exact_slope(self):
        t = np.arange(2000.0, 2015.0)
        self.assertTrue(np.allclose(trend.pairwise_slopes(t, 3.0 * t + 5), 3.0))

    def test_matches_scipy_theilslopes(self):
        from scipy import stats
        rng = np.random.default_rng(1)
        t = np.arange(2000.0, 2020.0)
        x = 0.5 * t + rng.normal(size=20)
        r = trend.analyze_trend(t, x)
        self.assertAlmostEqual(r["sen"]["slope_per_year"], stats.theilslopes(x, t)[0], places=10)

    def test_robust_to_an_outlier_unlike_regression(self):
        t = np.arange(2000.0, 2020.0)
        x = 2.0 * (t - 2000) + 50.0
        x[19] += 5000.0
        r = trend.analyze_trend(t, x)
        self.assertAlmostEqual(r["sen"]["slope_per_year"], 2.0, delta=0.1)
        self.assertGreater(abs(r["ols"]["slope_per_year"] - 2.0), 5.0)

    def test_confidence_interval_coverage(self):
        rng = np.random.default_rng(2024)
        t = np.arange(20.0)
        hits = 0
        for _ in range(600):
            r = trend.analyze_trend(t, 2.0 * t + rng.normal(0, 5, 20), min_years=5)
            hits += r["sen"]["ci_low"] <= 2.0 <= r["sen"]["ci_high"]
        self.assertTrue(0.90 <= hits / 600.0 <= 0.99, hits / 600.0)

    def test_gaps_in_time_use_real_dates(self):
        t = np.array([2000, 2001, 2002, 2005, 2006, 2007, 2010, 2011, 2012, 2013, 2014, 2015.0])
        r = trend.analyze_trend(t, 2.0 * t + 1.0)
        self.assertAlmostEqual(r["sen"]["slope_per_year"], 2.0)
        self.assertEqual(r["direction"], "increasing")


class Classification(unittest.TestCase):
    t = np.arange(2005.0, 2025.0)

    def test_increasing(self):
        x = 100 + 2.0 * (self.t - 2005) + np.random.default_rng(3).normal(0, 3, 20)
        r = trend.analyze_trend(self.t, x)
        self.assertEqual((r["direction"], r["significant"]), ("increasing", True))
        self.assertAlmostEqual(r["sen"]["slope_per_year"], 2.0, delta=0.6)
        self.assertEqual(r["direction_label"], "Aumento")

    def test_decreasing(self):
        x = 100 - 1.5 * (self.t - 2005) + np.random.default_rng(4).normal(0, 2, 20)
        r = trend.analyze_trend(self.t, x)
        self.assertEqual(r["direction"], "decreasing")
        self.assertLess(r["sen"]["slope_per_year"], 0)

    def test_no_trend_in_noise(self):
        r = trend.analyze_trend(self.t, np.random.default_rng(11).normal(size=20))
        self.assertEqual(r["direction"], "no_trend")
        self.assertFalse(r["significant"])
        self.assertGreater(r["mann_kendall"]["p_value"], 0.05)

    def test_too_few_years_is_inconclusive_not_a_guess(self):
        r = trend.analyze_trend(self.t[:6], np.arange(6.0), min_years=10)
        self.assertEqual(r["direction"], "inconclusive")
        self.assertIn("insuficientes", r["reason"])
        self.assertIsNone(r["sen"])

    def test_constant_series_is_inconclusive(self):
        r = trend.analyze_trend(self.t, np.full(20, 7.0))
        self.assertEqual(r["direction"], "inconclusive")
        self.assertIn("constante", r["reason"])

    def test_nan_values_are_ignored_and_counted(self):
        x = 100 + 2.0 * (self.t - 2005) + np.random.default_rng(5).normal(0, 2, 20)
        x_nan = x.copy()
        x_nan[[3, 8, 12]] = np.nan
        keep = ~np.isnan(x_nan)
        a = trend.analyze_trend(self.t, x_nan, expected_n=20)
        b = trend.analyze_trend(self.t[keep], x[keep])
        self.assertEqual(a["n_observations"], 17)
        self.assertEqual(a["sen"]["slope_per_year"], b["sen"]["slope_per_year"])
        self.assertEqual(a["mann_kendall"]["p_value"], b["mann_kendall"]["p_value"])
        self.assertTrue(any("Faltam" in w for w in a["warnings"]))

    def test_positive_autocorrelation_is_flagged(self):
        rng = np.random.default_rng(8)
        x = np.zeros(60)
        for i in range(1, 60):
            x[i] = 0.8 * x[i - 1] + rng.normal()
        r = trend.analyze_trend(np.arange(1960.0, 2020.0), x)
        self.assertGreater(r["autocorrelation_lag1"], 0.4)
        self.assertTrue(any("Autocorrelação positiva" in w for w in r["warnings"]))

    def test_regression_slope_matches_numpy(self):
        x = 5 + 0.7 * (self.t - 2005) + np.random.default_rng(6).normal(0, 1, 20)
        r = trend.analyze_trend(self.t, x)
        self.assertAlmostEqual(r["ols"]["slope_per_year"], np.polyfit(self.t, x, 1)[0], places=9)


class Seasonal(unittest.TestCase):
    @staticmethod
    def monthly(years, slope, noise, seed):
        rng = np.random.default_rng(seed)
        t, x, m = [], [], []
        for y in range(2005, 2005 + years):
            for mo in range(1, 13):
                t.append(y + (mo - 1) / 12.0)
                m.append(mo)
                x.append(100 + 80 * math.sin(2 * math.pi * (mo - 1) / 12) + slope * (y - 2005)
                         + rng.normal(0, noise))
        return np.array(t), np.array(x), np.array(m)

    def test_detects_trend_under_a_strong_seasonal_cycle(self):
        t, x, m = self.monthly(15, 1.5, 10, 1)
        r = trend.analyze_trend(t, x, season=m, step=1 / 12.0)
        self.assertEqual(r["direction"], "increasing")
        self.assertAlmostEqual(r["sen"]["slope_per_year"], 1.5, delta=0.3)
        self.assertIn("sazonal", r["method"])
        self.assertTrue(any("independência" in s for s in r["limitations"]))

    def test_statistic_is_the_sum_of_the_per_month_statistics(self):
        t, x, m = self.monthly(12, 0.4, 10, 2)
        r = trend.analyze_trend(t, x, season=m, step=1 / 12.0)
        parts = [brute_mk(list(x[m == k])) for k in range(1, 13)]
        self.assertEqual(r["mann_kendall"]["s"], sum(p[0] for p in parts))
        self.assertAlmostEqual(r["mann_kendall"]["var_s"], sum(p[1] for p in parts))

    def test_false_positive_rate_without_trend(self):
        hits = 0
        for seed in range(300):
            t, x, m = self.monthly(12, 0.0, 10, 1000 + seed)
            hits += trend.analyze_trend(t, x, season=m, step=1 / 12.0)["significant"]
        self.assertTrue(0.02 <= hits / 300.0 <= 0.09, hits / 300.0)


if __name__ == "__main__":
    unittest.main()
