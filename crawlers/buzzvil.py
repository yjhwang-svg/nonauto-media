"""
Buzzvil 대시보드 크롤러
- 전일자 Impressions / Clicks / Spent Budget 수집
- adgroup_id는 Google Sheets '설정' 탭 또는 config.json에서 읽음
"""

import os
import re
import time
import logging
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

LOGIN_URL = "https://dashboard.buzzvil.com/login"
REPORT_URL_TEMPLATE = "https://dashboard.buzzvil.com/campaign/direct_sales/adgroups/{adgroup_id}/report"


def build_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-zygote")
    options.add_argument("--single-process")
    return webdriver.Chrome(options=options)


def login(driver):
    logger.info("Buzzvil 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    email_input = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[type="email"], input[name="email"], input[name="username"]')
        )
    )
    email_input.clear()
    email_input.send_keys(os.environ["BUZZVIL_EMAIL"])

    password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    password_input.clear()
    password_input.send_keys(os.environ["BUZZVIL_PASSWORD"])

    submit_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    submit_btn.click()

    # 로그인 후 대시보드 이동 대기
    try:
        wait.until(EC.url_changes(LOGIN_URL))
    except TimeoutException:
        pass
    logger.info("Buzzvil 로그인 성공")
    time.sleep(2)


def _clean_number(text: str) -> int:
    """'81,444' → 81444, '₩350,210' → 350210"""
    cleaned = re.sub(r"[^\d]", "", text.strip())
    return int(cleaned) if cleaned else 0


def _get_header_indices(header_cells: list) -> dict:
    """
    헤더 행에서 Date / Impressions / Clicks / Spent Budget 컬럼 인덱스 탐지.
    """
    mapping = {}
    for i, cell in enumerate(header_cells):
        text = cell.text.strip().lower()
        if "date" in text:
            mapping["date"] = i
        elif "impression" in text:
            mapping["imps"] = i
        elif "click" in text:
            mapping["clicks"] = i
        elif "spent" in text or "budget" in text or "spend" in text:
            mapping["cost"] = i
    return mapping


def _parse_date(text: str) -> str:
    """
    다양한 날짜 포맷을 YYYY-MM-DD로 정규화.
    지원: YYYY-MM-DD, MM/DD/YYYY, YYYY.MM.DD
    """
    text = text.strip()
    # YYYY-MM-DD 이미 표준 형식
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    # MM/DD/YYYY
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    # YYYY.MM.DD
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return text


def get_yesterday_data(driver, adgroup_id: str) -> dict | None:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    report_url = REPORT_URL_TEMPLATE.format(adgroup_id=adgroup_id)
    logger.info(f"[Buzzvil] {yesterday} 데이터 수집 시작: {report_url}")

    driver.get(report_url)
    wait = WebDriverWait(driver, 40)

    # 테이블 로드 대기
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
    except TimeoutException:
        logger.warning("[Buzzvil] 테이블 로드 타임아웃. 계속 진행.")
    time.sleep(4)

    # 헤더 인덱스 파악
    try:
        header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th, table thead td")
        col = _get_header_indices(header_cells)
        logger.info(f"[Buzzvil] 컬럼 인덱스: {col}")
    except Exception as e:
        logger.error(f"[Buzzvil] 헤더 파싱 실패: {e}")
        col = {"date": 0, "imps": 1, "clicks": 2, "cost": 3}

    # 데이터 행 탐색
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    logger.info(f"[Buzzvil] 테이블 행 수: {len(rows)}")

    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if not cells:
            continue

        date_idx = col.get("date", 0)
        if date_idx >= len(cells):
            continue

        raw_date = cells[date_idx].text.strip()
        normalized = _parse_date(raw_date)
        if yesterday not in normalized:
            continue

        try:
            imps   = _clean_number(cells[col.get("imps",   1)].text)
            clicks = _clean_number(cells[col.get("clicks", 2)].text)
            cost   = _clean_number(cells[col.get("cost",   3)].text)

            logger.info(f"[Buzzvil] 수집 완료 → imps={imps}, clicks={clicks}, cost={cost}")
            return {"imps": imps, "clicks": clicks, "cost": cost}
        except (IndexError, ValueError) as e:
            logger.error(f"[Buzzvil] 셀 파싱 오류: {e}")
            return None

    logger.warning(f"[Buzzvil] 날짜 {yesterday}에 해당하는 행 없음")
    return None


def scrape(adgroup_id: str) -> dict | None:
    """
    Buzzvil 대시보드에서 전일자 데이터를 수집.
    Returns: data dict or None
    """
    driver = build_driver()
    try:
        login(driver)
        return get_yesterday_data(driver, adgroup_id)
    except Exception as e:
        logger.error(f"Buzzvil 크롤링 오류: {e}")
        return None
    finally:
        driver.quit()
