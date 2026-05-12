"""
RTB House API 응답 파싱 테스트 (구 Selenium 텍스트 파싱 테스트 대체)
"""
import unittest
from unittest.mock import patch, MagicMock

from crawlers.rtbhouse import fetch_day_totals, _extract_hash_from_url


class RTBHouseApiParsingTests(unittest.TestCase):
    def test_extract_hash_from_url(self):
        url = "https://panel.rtbhouse.com/dashboard/zjgMiqEIsN3oQNMPG6hc?groupBy=day"
        self.assertEqual(_extract_hash_from_url(url), "zjgMiqEIsN3oQNMPG6hc")

    def test_extract_hash_from_url_no_query(self):
        url = "https://panel.rtbhouse.com/dashboard/0nxXCRelH0yCnjinL3tE"
        self.assertEqual(_extract_hash_from_url(url), "0nxXCRelH0yCnjinL3tE")

    def test_fetch_day_totals_sums_rows(self):
        fake_rows = [
            {"impsCount": "57022", "clicksCount": "11842", "campaignCost": "148269.44"},
            {"impsCount": "1000",  "clicksCount": "100",   "campaignCost": "500.56"},
        ]
        with patch("crawlers.rtbhouse._call_api", return_value=fake_rows), \
             patch("crawlers.rtbhouse._get_credentials", return_value=("u@example.com", "pw")):
            result = fetch_day_totals("someHash", "2026-05-05", "APP")

        self.assertEqual(result["imps"],   58022)
        self.assertEqual(result["clicks"], 11942)
        self.assertEqual(result["cost"],   148770)  # int(round(148269.44 + 500.56))

    def test_fetch_day_totals_returns_none_on_empty(self):
        with patch("crawlers.rtbhouse._call_api", return_value=[]), \
             patch("crawlers.rtbhouse._get_credentials", return_value=("u@example.com", "pw")):
            result = fetch_day_totals("someHash", "2026-05-05", "APP")

        self.assertIsNone(result)

    def test_fetch_day_totals_returns_none_on_api_error(self):
        with patch("crawlers.rtbhouse._call_api", side_effect=RuntimeError("API 오류")), \
             patch("crawlers.rtbhouse._get_credentials", return_value=("u@example.com", "pw")):
            result = fetch_day_totals("someHash", "2026-05-05", "APP")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
