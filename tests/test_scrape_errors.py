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

    def test_rtbhouse_scrape_returns_none_on_api_error(self):
        # API 방식: _call_api 실패 시 scrape()가 (None, None)을 반환해야 함
        with patch.object(rtbhouse, "_call_api", side_effect=RuntimeError("api error")), \
             patch.object(rtbhouse, "_get_credentials", return_value=("u@x.com", "pw")):
            app_data, web_data = rtbhouse.scrape(
                "https://panel.rtbhouse.com/dashboard/appHash?x=1",
                "https://panel.rtbhouse.com/dashboard/webHash?x=1",
            )

        self.assertIsNone(app_data)
        self.assertIsNone(web_data)


if __name__ == "__main__":
    unittest.main()
