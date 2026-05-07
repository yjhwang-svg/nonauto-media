import unittest

from crawlers.auth import assert_login_form_absent, is_login_page, require_env


class FakeField:
    def __init__(self, visible):
        self.visible = visible

    def is_displayed(self):
        return self.visible


class FakeDriver:
    current_url = "https://panel.rtbhouse.com/login"
    title = "Sign in | RTB House Reports"

    def __init__(self, fields):
        self.fields = fields

    def find_elements(self, by, selector):
        return self.fields


class LoginStateTests(unittest.TestCase):
    def test_detects_rtbhouse_login_page_after_failed_submit(self):
        self.assertTrue(
            is_login_page(
                "https://panel.rtbhouse.com/login",
                "Sign in | RTB House Reports",
            )
        )

    def test_does_not_treat_dashboard_as_login_page(self):
        self.assertFalse(
            is_login_page(
                "https://panel.rtbhouse.com/dashboard/zjgMiqEIsN3oQNMPG6hc",
                "RTB House Reports",
            )
        )

    def test_require_env_rejects_blank_secret(self):
        with self.assertRaises(ValueError):
            require_env("RTBHOUSE_EMAIL", {"RTBHOUSE_EMAIL": "   "})

    def test_login_url_without_visible_form_can_still_be_authenticated_shell(self):
        driver = FakeDriver([])

        assert_login_form_absent(driver, "RTB House", 'input[name="login"]')

    def test_visible_login_form_is_a_login_failure(self):
        driver = FakeDriver([FakeField(True)])

        with self.assertRaisesRegex(RuntimeError, "로그인 실패"):
            assert_login_form_absent(driver, "RTB House", 'input[name="login"]')


if __name__ == "__main__":
    unittest.main()
