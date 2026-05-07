import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from utils.dates import get_target_date


class TargetDateTests(unittest.TestCase):
    def test_uses_korean_business_day_when_runner_clock_is_utc(self):
        github_runner_time = datetime(2026, 5, 5, 23, 52, tzinfo=timezone.utc)

        self.assertEqual(get_target_date(now=github_runner_time), "2026-05-05")

    def test_allows_explicit_target_date_override(self):
        with patch.dict(os.environ, {"TARGET_DATE": "2026-05-04"}):
            self.assertEqual(get_target_date(), "2026-05-04")

    def test_rejects_invalid_target_date_override(self):
        with patch.dict(os.environ, {"TARGET_DATE": "2026/05/04"}):
            with self.assertRaises(ValueError):
                get_target_date()


if __name__ == "__main__":
    unittest.main()
