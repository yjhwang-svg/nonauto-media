import unittest
from unittest.mock import patch

from crawlers import buzzvil, rtbhouse


class FakeDriver:
    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


class ScrapeErrorTests(unittest.TestCase):
    def test_buzzvil_scrape_propagates_login_failure(self):
        driver = FakeDriver()

        with patch.object(buzzvil, "build_driver", return_value=driver):
            with patch.object(buzzvil, "login", side_effect=RuntimeError("login failed")):
                with self.assertRaisesRegex(RuntimeError, "login failed"):
                    buzzvil.scrape("55015", target_date="2026-05-05")

        self.assertTrue(driver.quit_called)

    def test_rtbhouse_scrape_propagates_login_failure(self):
        driver = FakeDriver()

        with patch.object(rtbhouse, "build_driver", return_value=driver):
            with patch.object(rtbhouse, "login", side_effect=RuntimeError("login failed")):
                with self.assertRaisesRegex(RuntimeError, "login failed"):
                    rtbhouse.scrape("https://example.com/app", "https://example.com/web", target_date="2026-05-05")

        self.assertTrue(driver.quit_called)


if __name__ == "__main__":
    unittest.main()
