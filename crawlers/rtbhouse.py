"""
RTB House 대시보드 크롤러
- APP / WEB 각각 전일자 Imps / Clicks / Cost(KRW) 수집
"""

import re
import time
import logging

from crawlers.auth import assert_login_form_absent, require_env
from utils.dates import get_target_date

logger = logging.getLogger(__name__)

LOGIN_URL = "https://panel.rtbhouse.com/login"


def build_driver():
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    return webdriver.Firefox(options=options)


def login(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    logger.info("RTB House 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    # ── 진단: 페이지 로드 후 상태 출력 ──────────────────────────────
    time.sleep(3)
    logger.info(f"현재 URL: {driver.current_url}")
    logger.info(f"페이지 제목: {driver.title}")

    # 스크린샷 저장 (GitHub Actions artifact로 확인 가능)
    try:
        driver.save_screenshot("/tmp/rtbhouse_login.png")
        logger.info("스크린샷 저장: /tmp/rtbhouse_login.png")
    except Exception as e:
        logger.warning(f"스크린샷 저장 실패: {e}")

    # 페이지에 있는 모든 input 출력
    all_inputs = driver.find_elements(By.TAG_NAME, "input")
    logger.info(f"페이지 내 input 개수: {len(all_inputs)}")
    for i, inp in enumerate(all_inputs):
        logger.info(f"  input[{i}] type={inp.get_attribute('type')} name={inp.get_attribute('name')} id={inp.get_attribute('id')} placeholder={inp.get_attribute('placeholder')}")
    # ─────────────────────────────────────────────────────────────────

    # 로그인 폼 입력 (확인된 셀렉터 사용)
    email_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="login"]'))
    )
    email_input.clear()
    email_input.send_keys(require_env("RTBHOUSE_EMAIL"))

    password_input = driver.find_element(By.CSS_SELECTOR, 'input[name="password"]')
    password_input.clear()
    password_input.send_keys(require_env("RTBHOUSE_PASSWORD"))

    # Enter 키로 제출 (React 이벤트 트리거에 더 안정적)
    from selenium.webdriver.common.keys import Keys
    password_input.send_keys(Keys.RETURN)
    logger.info("로그인 폼 제출 (Enter)")

    # 제출 후 5초 대기 후 스크린샷 (로그인 성공/실패 확인)
    time.sleep(5)
    try:
        driver.save_screenshot("/tmp/rtbhouse_after_submit.png")
        logger.info(f"제출 후 URL: {driver.current_url}")
        logger.info(f"제출 후 제목: {driver.title}")
    except Exception:
        pass

    # 페이지에 에러 메시지가 있는지 확인
    error_selectors = ["[class*='error']", "[class*='Error']", "[role='alert']", ".alert"]
    for sel in error_selectors:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        for el in elems:
            if el.text.strip():
                logger.warning(f"페이지 오류 메시지 감지: '{el.text.strip()}'")

    # 인증 완료 대기 — 로그인 화면을 벗어나야 성공
    try:
        WebDriverWait(driver, 20).until(
            lambda d: not ("/login" in d.current_url.lower() or "/auth/login" in d.current_url.lower())
        )
    except TimeoutException:
        pass

    assert_login_form_absent(driver, "RTB House", 'input[name="login"], input[name="password"]')
    logger.info(f"RTB House 로그인 완료 — URL: {driver.current_url}")
    time.sleep(3)


def _clean_number(text: str) -> int:
    """'57,022' -> 57022, '319 808.82' -> 319809."""
    normalized = text.strip().replace(",", "").replace(" ", "")
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    return round(float(match.group(0))) if match else 0


def _parse_visible_text_row(body_text: str, target_date: str) -> dict | None:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if target_date not in line:
            continue

        values = []
        for candidate in lines[index + 1:]:
            if re.match(r"\d{4}-\d{2}-\d{2}", candidate):
                break
            values.append(candidate)
            if len(values) >= 4:
                return {
                    "imps": _clean_number(values[0]),
                    "clicks": _clean_number(values[1]),
                    "cost": _clean_number(values[3]),
                }
    return None


def _get_header_indices(header_cells: list) -> dict:
    """
    헤더 행에서 Date / Imps / Clicks / Cost 컬럼 인덱스를 탐지.
    RTB House 대시보드 컬럼명이 바뀌어도 키워드로 매칭.
    """
    mapping = {}
    for i, cell in enumerate(header_cells):
        text = cell.text.strip().lower()
        if "date" in text:
            mapping["date"] = i
        elif "imp" in text:
            mapping["imps"] = i
        elif "click" in text:
            mapping["clicks"] = i
        elif "cost" in text or "krw" in text or "spend" in text:
            mapping["cost"] = i
    return mapping


def get_yesterday_data(driver, dashboard_url: str, label: str, target_date: str | None = None) -> dict | None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    target_date = target_date or get_target_date()
    logger.info(f"[RTB {label}] {target_date} 데이터 수집 시작: {dashboard_url}")

    driver.get(dashboard_url)
    wait = WebDriverWait(driver, 40)

    # SPA 렌더링 대기 — table 또는 role=grid 중 먼저 나타나는 것
    TABLE_SELECTORS = [
        "table",
        "[role='grid']",
        "[role='table']",
        "[role='row']",
    ]
    loaded = False
    for sel in TABLE_SELECTORS:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            logger.info(f"[RTB {label}] 테이블 감지 셀렉터: {sel}")
            loaded = True
            break
        except TimeoutException:
            wait = WebDriverWait(driver, 10)
    if not loaded:
        logger.warning(f"[RTB {label}] 테이블 미감지 — 현재 URL: {driver.current_url}")

    time.sleep(4)

    # 스크린샷 저장 (dashboard 상태 확인용)
    try:
        driver.save_screenshot(f"/tmp/rtbhouse_{label.lower()}_dashboard.png")
    except Exception:
        pass

    # 페이지 구조 진단 로그
    logger.info(f"[RTB {label}] 현재 URL: {driver.current_url}")
    for sel in ["table", "[role='grid']", "[role='row']", "[role='columnheader']"]:
        count = len(driver.find_elements(By.CSS_SELECTOR, sel))
        if count:
            logger.info(f"[RTB {label}] '{sel}' 요소 수: {count}")

    # 헤더 인덱스 파악 — table 또는 role=columnheader 시도
    HEADER_SELECTORS = [
        "table thead th",
        "table thead td",
        "[role='columnheader']",
        "[role='gridcell']:first-child",
    ]
    header_cells = []
    for sel in HEADER_SELECTORS:
        header_cells = driver.find_elements(By.CSS_SELECTOR, sel)
        if header_cells:
            logger.info(f"[RTB {label}] 헤더 셀렉터 성공: {sel} ({len(header_cells)}개)")
            break

    col = _get_header_indices(header_cells)
    logger.info(f"[RTB {label}] 컬럼 인덱스: {col}")

    # 데이터 행 탐색 — table tr 또는 role=row 시도
    ROW_SELECTORS = [
        "table tbody tr",
        "[role='row']",
    ]
    rows = []
    for sel in ROW_SELECTORS:
        rows = driver.find_elements(By.CSS_SELECTOR, sel)
        if rows:
            logger.info(f"[RTB {label}] 행 셀렉터 성공: {sel}")
            break
    logger.info(f"[RTB {label}] 테이블 행 수: {len(rows)}")

    for row in rows:
        # table td 또는 role=gridcell 시도
        cells = row.find_elements(By.CSS_SELECTOR, "td, [role='gridcell']")
        if not cells:
            continue

        date_idx = col.get("date", 0)
        if date_idx >= len(cells):
            continue

        date_text = cells[date_idx].text.strip()
        if target_date not in date_text:
            continue

        try:
            imps   = _clean_number(cells[col.get("imps",   1)].text)
            clicks = _clean_number(cells[col.get("clicks", 2)].text)
            cost   = _clean_number(cells[col.get("cost",   3)].text)

            logger.info(f"[RTB {label}] 수집 완료 → imps={imps}, clicks={clicks}, cost={cost}")
            return {"imps": imps, "clicks": clicks, "cost": cost}
        except (IndexError, ValueError) as e:
            logger.error(f"[RTB {label}] 셀 파싱 오류: {e}")
            return None

    try:
        fallback_data = _parse_visible_text_row(driver.find_element(By.TAG_NAME, "body").text, target_date)
    except Exception:
        fallback_data = None
    if fallback_data:
        logger.info(
            f"[RTB {label}] 화면 텍스트 fallback 수집 완료 → "
            f"imps={fallback_data['imps']}, clicks={fallback_data['clicks']}, cost={fallback_data['cost']}"
        )
        return fallback_data

    logger.warning(f"[RTB {label}] 날짜 {target_date}에 해당하는 행 없음")
    return None


def scrape(app_url: str, web_url: str, target_date: str | None = None) -> tuple[dict | None, dict | None]:
    """
    RTB House APP / WEB 대시보드에서 전일자 데이터를 수집.
    Returns: (app_data, web_data) — 실패 시 None
    """
    driver = build_driver()
    try:
        login(driver)
        app_data = get_yesterday_data(driver, app_url, "APP", target_date=target_date)
        web_data = get_yesterday_data(driver, web_url, "WEB", target_date=target_date)
        return app_data, web_data
    finally:
        driver.quit()
