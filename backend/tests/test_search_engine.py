import unittest

from app.data.search_engine import search_catalog, engine_status, normalize


class CatalogSearchTests(unittest.TestCase):
    def setUp(self):
        self.datasets = [
            {"id": "rain", "name": "Rainfall monthly", "variable_label": "Precipitation", "provider": "NASA", "status": "available", "coverage_start": "2000-01", "coverage_end": "2025-01", "native_unit": "mm"},
            {"id": "ndvi", "name": "Vegetation index", "variable_label": "NDVI", "provider": "MODIS", "status": "planned"},
        ]

    def test_accent_and_whitespace_normalization(self):
        self.assertEqual(normalize("Humidade_do_solo"), "humidade do solo")

    def test_query_matches_metadata_and_returns_provenance(self):
        matches = search_catalog(self.datasets, "precipitation")
        self.assertEqual([item["id"] for item in matches], ["rain"])
        self.assertEqual(matches[0]["provider"], "NASA")
        self.assertEqual(matches[0]["status"], "available")

    def test_empty_query_returns_catalog_items(self):
        self.assertEqual(len(search_catalog(self.datasets, "")), 2)

    def test_planned_item_is_not_promoted_to_available(self):
        matches = search_catalog(self.datasets, "NDVI")
        self.assertEqual(matches[0]["status"], "planned")

    def test_provider_status_discloses_phase(self):
        status = engine_status()
        self.assertEqual(status["phase"], "catalog_search")
        self.assertTrue(any(p["id"] == "earth_engine" and p["status"] == "active" for p in status["providers"]))


if __name__ == "__main__":
    unittest.main()
