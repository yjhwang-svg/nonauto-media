"""
RTB House 대시보드 크롤러
- APP / WEB 각각 전일자 Imps / Clicks / Cost(KRW) 수집
"""

import os
import re
import time
import logging
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

LOGIN_URL = "https://panel.rtbhouse.com/login"


def build_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    return webdriver.Firefox(options=options)


def login(driver):
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
    email_input.send_keys(os.environ["RTBHOUSE_EMAIL"])

    password_input = driver.find_element(By.CSS_SELECTOR, 'input[name="password"]')
    password_input.clear()
    password_input.send_keys(os.environ["RTBHOUSE_PASSWORD"])

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

    # 인증 완료 대기 — URL이 /auth/ 에서 벗어나면 성공
    try:
        WebDriverWait(driver, 20).until(
            lambda d: "/auth/" not in d.current_url.lower()
        )
    except TimeoutException:
        pass

    logger.info(f"RTB House 로그인 완료 — URL: {driver.current_url}")
    time.sleep(3)


def _clean_number(text: str) -> int:
    """'57,022' → 57022, '148,269 KRW' → 148269"""
    cleaned = re.sub(r"[^\d]", "", text.strip())
    return int(cleaned) if cleaned else 0


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


def get_yesterday_data(driver, dashboard_url: str, label: str) -> dict | None:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"[RTB {label}] {yesterday} 데이터 수집 시작: {dashboard_url}")

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
        if yesterday not in date_text:
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

    logger.warning(f"[RTB {label}] 날짜 {yesterday}에 해당하는 행 없음")
    return None


def scrape(app_url: str, web_url: str) -> tuple[dict | None, dict | None]:
    """
    RTB House APP / WEB 대시보드에서 전일자 데이터를 수집.
    Returns: (app_data, web_data) — 실패 시 None
    """
    driver = build_driver()
    try:
        login(driver)
        app_data = get_yesterday_data(driver, app_url, "APP")
        web_data = get_yesterday_data(driver, web_url, "WEB")
        return app_data, web_data
    except Exception as e:
        logger.error(f"RTB House 크롤링 오류: {e}")
        return None, None
    finally:
        driver.quit()
