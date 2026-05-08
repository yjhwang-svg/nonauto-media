import unittest

from crawlers.buzzvil import _parse_date


class BuzzvilDateParsingTests(unittest.TestCase):
    def test_parses_english_month_day_year(self):
        self.assertEqual(_parse_date("May 4, 2026"), "2026-05-04")

    def test_parses_korean_year_month_day(self):
        self.assertEqual(_parse_date("2026년 5월 4일"), "2026-05-04")


if __name__ == "__main__":
    unittest.main()
