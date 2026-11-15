import json
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.data.earth_engine import EarthEngineLoader


class EarthEngineInitialization(unittest.TestCase):
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
