import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.data.earth_engine import EarthEngineLoader
from app.errors import ApiError


class EarthEngineInitialization(unittest.TestCase):
    def test_map_permission_error_is_sanitized(self):
        with self.assertRaises(ApiError) as ctx:
            EarthEngineLoader._raise_map_error(
                {"name": "NASA GPM"},
                RuntimeError("Permission 'earthengine.thumbnails.create' denied on project"),
            )
        self.assertEqual(ctx.exception.code, "earth_engine_permission_denied")
        self.assertNotIn("thumbnails.create", ctx.exception.message)

    def test_other_map_errors_do_not_expose_raw_details(self):
        with self.assertRaises(Exception) as ctx:
            EarthEngineLoader._raise_map_error(
                {"name": "NASA GPM"},
                RuntimeError("internal endpoint https://example.invalid/private"),
            )
        self.assertEqual(ctx.exception.code, "earth_engine_map_failed")
        self.assertNotIn("example.invalid", ctx.exception.message)

    def test_deadline_is_set_only_after_initialize(self):
        events = []
        fake_ee = SimpleNamespace(
            Initialize=lambda credentials, project: events.append(("initialize", project)),
            data=SimpleNamespace(setDeadline=lambda milliseconds: events.append(("deadline", milliseconds))),
        )
        with tempfile.TemporaryDirectory() as tmp:
            loader = EarthEngineLoader(
                raw_dir=tmp,
                regions_dir=tmp,
                project_id="earth-trend-test",
                service_account_json=json.dumps({}),
            )
            with patch.dict(sys.modules, {"ee": fake_ee}), patch(
                "google.oauth2.service_account.Credentials.from_service_account_info",
                return_value=object(),
            ):
                self.assertIs(loader._client(), fake_ee)

        self.assertEqual(events, [
            ("initialize", "earth-trend-test"),
            ("deadline", 90_000),
        ])


if __name__ == "__main__":
    unittest.main()
