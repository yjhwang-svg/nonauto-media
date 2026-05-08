import os
from collections.abc import Mapping
from urllib.parse import urlparse


def require_env(name: str, env: Mapping[str, str] | None = None) -> str:
    source = os.environ if env is None else env
    value = source.get(name, "")
    if not value or not value.strip():
        raise ValueError(f"환경변수 {name}가 설정되지 않았거나 비어 있습니다.")
    return value


def is_login_page(url: str, title: str = "") -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").lower()
    normalized_title = title.strip().lower()

    if path.endswith("/login") or path.endswith("/auth/login"):
        return True
    return "sign in" in normalized_title or normalized_title == "login"


def assert_logged_in(driver, service_name: str):
    if is_login_page(driver.current_url, driver.title):
        raise RuntimeError(
            f"{service_name} 로그인 실패: 제출 후에도 로그인 페이지에 머물러 있습니다. "
            f"GitHub Secrets 값, 2FA/CAPTCHA, 또는 CI IP 차단 여부를 확인하세요. "
            f"URL={driver.current_url!r}, title={driver.title!r}"
        )


def assert_login_form_absent(driver, service_name: str, selector: str):
    fields = driver.find_elements("css selector", selector)
    visible_fields = [field for field in fields if field.is_displayed()]
    if visible_fields:
        raise RuntimeError(
            f"{service_name} 로그인 실패: 제출 후에도 로그인 입력 폼이 남아 있습니다. "
            f"GitHub Secrets 값, 2FA/CAPTCHA, 또는 CI IP 차단 여부를 확인하세요. "
            f"URL={driver.current_url!r}, title={driver.title!r}"
        )
