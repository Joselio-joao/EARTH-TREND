import tempfile
import unittest
from pathlib import Path

from app.ml.online import OnlineLearningStore


def sample(values=None, slope=0.05, p_value=0.4):
    return {
        "series": {"values": values or [10.0, 10.5, 9.8, 10.2, 10.1]},
        "period": {"n_years": 20},
        "trend": {
            "sen": {"slope_per_year": slope},
            "mann_kendall": {"p_value": p_value},
        },
    }


class OnlineLearningTests(unittest.TestCase):
    def test_waits_for_minimum_real_analyses_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            learner = OnlineLearningStore(Path(directory))
            for index in range(7):
                result = learner.observe("gpm_imerg_monthly", "annual", sample(slope=0.05 + index * 0.001))
                self.assertEqual(result["status"], "learning")
            ready = learner.observe("gpm_imerg_monthly", "annual", sample(slope=0.054))
            self.assertEqual(ready["status"], "ready")
            self.assertEqual(ready["training_examples"], 8)

            reloaded = OnlineLearningStore(Path(directory))
            status = reloaded.status()
            self.assertEqual(status["model_count"], 1)
            self.assertEqual(status["models"][0]["training_examples"], 8)
            self.assertEqual(status["models"][0]["status"], "ready")

    def test_flags_an_unusual_signature_after_training(self):
        with tempfile.TemporaryDirectory() as directory:
            learner = OnlineLearningStore(Path(directory))
            for _ in range(8):
                learner.observe("gpm_imerg_monthly", "annual", sample())
            unusual = learner.observe(
                "gpm_imerg_monthly", "annual",
                sample(values=[1, 20, 300, 4, 900], slope=25.0, p_value=0.001),
            )
            self.assertTrue(unusual["is_unusual"])
            self.assertGreater(unusual["anomaly_score"], unusual["threshold"])

    def test_does_not_train_without_a_valid_time_series(self):
        with tempfile.TemporaryDirectory() as directory:
            learner = OnlineLearningStore(Path(directory))
            result = learner.observe("modis_ndvi", "annual", {"status": "inconclusive", "series": {"values": [10, 11, 12]}})
            self.assertEqual(result["status"], "insufficient_data")
            self.assertEqual(learner.status()["model_count"], 0)


if __name__ == "__main__":
    unittest.main()
