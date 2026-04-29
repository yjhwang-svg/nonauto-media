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

    # 이메일 입력 — 여러 셀렉터를 순서대로 시도
    email_selectors = [
        'input[type="email"]',
        'input[name="email"]',
        'input[name="username"]',
        'input[name="login"]',
        'input[type="text"]',
    ]
    email_input = None
    for sel in email_selectors:
        try:
            email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            logger.info(f"이메일 입력 셀렉터 성공: {sel}")
            break
        except TimeoutException:
            logger.warning(f"이메일 셀렉터 실패: {sel}")
            wait = WebDriverWait(driver, 5)  # 이후 시도는 5초씩

    if not email_input:
        raise Exception("이메일 입력 필드를 찾을 수 없음")

    email_input.clear()
    email_input.send_keys(os.environ["RTBHOUSE_EMAIL"])

    password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    password_input.clear()
    password_input.send_keys(os.environ["RTBHOUSE_PASSWORD"])

    submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    submit_btn.click()

    # 로그인 완료 대기
    try:
        WebDriverWait(driver, 20).until(EC.url_changes(driver.current_url))
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

    # 테이블 로드 대기
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
    except TimeoutException:
        logger.warning(f"[RTB {label}] 테이블 로드 대기 중 타임아웃. 계속 진행.")
    time.sleep(4)  # SPA 렌더링 추가 대기

    # 헤더 인덱스 파악
    try:
        header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th, table thead td")
        col = _get_header_indices(header_cells)
        logger.info(f"[RTB {label}] 컬럼 인덱스: {col}")
    except Exception as e:
        logger.error(f"[RTB {label}] 헤더 파싱 실패: {e}")
        col = {"date": 0, "imps": 1, "clicks": 2, "cost": 3}

    # 데이터 행 탐색
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    logger.info(f"[RTB {label}] 테이블 행 수: {len(rows)}")

    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "td")
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
