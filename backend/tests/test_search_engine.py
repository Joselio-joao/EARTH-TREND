import unittest
from unittest.mock import Mock, patch

from app.data.search_engine import (CatalogProviderError, _COLLECTIONS_CACHE, _ITEMS_CACHE, engine_status,
                                    normalize, search_catalog, search_copernicus_collections, search_copernicus_items)


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

    def test_copernicus_collection_search_returns_live_metadata(self):
        _COLLECTIONS_CACHE.clear()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "collections": [{
                "id": "sentinel-2-l2a",
                "title": "Sentinel-2 Level-2A",
                "description": "Optical imagery.",
                "license": "other",
                "updated": "2026-11-20T00:00:00Z",
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [["2015-06-23T00:00:00Z", None]]},
                },
                "keywords": ["Sentinel", "optical"],
                "providers": [{"name": "ESA"}],
                "assets": {"thumbnail": {"href": "https://example.test/thumb.jpg"}},
            }]
        }
        with patch("app.data.search_engine.requests.get", return_value=response) as get:
            result = search_copernicus_collections("Sentinel-2", 5)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["id"], "sentinel-2-l2a")
        self.assertEqual(result["results"][0]["providers"], ["ESA"])
        self.assertEqual(result["results"][0]["catalog_status"], "live_metadata")
        self.assertEqual(result["retrieval"], "metadata_only")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "Sentinel-2")
        _COLLECTIONS_CACHE.clear()

    def test_copernicus_search_uses_cache(self):
        _COLLECTIONS_CACHE.clear()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"collections": []}
        with patch("app.data.search_engine.requests.get", return_value=response) as get:
            first = search_copernicus_collections("vegetation", 5)
            second = search_copernicus_collections("vegetation", 5)
        self.assertEqual(first, second)
        get.assert_called_once()
        _COLLECTIONS_CACHE.clear()

    def test_copernicus_provider_failure_is_explicit(self):
        _COLLECTIONS_CACHE.clear()
        with patch("app.data.search_engine.requests.get", side_effect=__import__("requests").Timeout):
            with self.assertRaises(CatalogProviderError):
                search_copernicus_collections("Sentinel", 5)
        _COLLECTIONS_CACHE.clear()

    def test_copernicus_items_returns_product_metadata_for_angola(self):
        _ITEMS_CACHE.clear()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "features": [{
                "id": "S2A_TEST_ITEM",
                "collection": "sentinel-2-l2a",
                "bbox": [12.1, -8.2, 12.8, -7.6],
                "properties": {
                    "datetime": "2026-10-10T09:35:31Z",
                    "platform": "sentinel-2a",
                    "instruments": ["msi"],
                    "eo:cloud_cover": 12.5,
                    "gsd": 10,
                    "processing:level": "L2A",
                    "product:type": "S2MSI2A",
                },
                "links": [{"rel": "self", "href": "https://stac.example/item/1"}],
            }],
            "links": [],
        }
        with patch("app.data.search_engine.requests.post", return_value=response) as post:
            result = search_copernicus_items("sentinel-2-l2a", "2026-10-01", "2026-10-31", 5)

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["items"][0]["id"], "S2A_TEST_ITEM")
        self.assertEqual(result["items"][0]["cloud_cover"], 12.5)
        self.assertEqual(result["items"][0]["gsd_m"], 10.0)
        self.assertEqual(result["items"][0]["item_url"], "https://stac.example/item/1")
        self.assertEqual(result["retrieval"], "metadata_only")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["collections"], ["sentinel-2-l2a"])
        self.assertEqual(body["datetime"], "2026-10-01T00:00:00Z/2026-10-31T23:59:59Z")
        self.assertEqual(body["intersects"]["type"], "MultiPolygon")
        _ITEMS_CACHE.clear()

    def test_copernicus_item_search_rejects_invalid_date_range(self):
        with self.assertRaises(ValueError):
            search_copernicus_items("sentinel-2-l2a", "2026-10-31", "2026-10-01", 5)

    def test_copernicus_item_search_rejects_ranges_over_one_year(self):
        with self.assertRaises(ValueError):
            search_copernicus_items("sentinel-2-l2a", "2024-01-01", "2025-01-03", 5)

    def test_provider_status_discloses_phase(self):
        status = engine_status()
        self.assertEqual(status["phase"], "catalog_search")
        self.assertTrue(any(p["id"] == "earth_engine" and p["status"] == "active" for p in status["providers"]))


if __name__ == "__main__":
    unittest.main()
