"""
메인 실행 스크립트
GitHub Actions 또는 Streamlit '지금 실행' 버튼에서 호출됨.

실행 흐름:
1. config.json + Google Sheets '설정' 탭에서 설정값 로드
2. RTB House APP / WEB 크롤링
3. Buzzvil 크롤링
4. Google Sheets '수기매체업로드' 시트에 5개 행 추가
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from crawlers import rtbhouse, buzzvil
from sheets import uploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_static_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def run() -> dict:
    """
    전체 크롤링 및 업로드 실행.
    반환값: 각 매체별 결과 요약 dict
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"=== 자동화 시작 | 대상 날짜: {yesterday} ===")

    static_cfg = load_static_config()
    spreadsheet_id   = static_cfg["spreadsheet_id"]
    data_sheet_name  = static_cfg["data_sheet_name"]
    config_sheet_name = static_cfg["config_sheet_name"]

    # Google Sheets '설정' 탭에서 adgroup_id 로드
    client = uploader.get_client()
    spreadsheet = uploader.get_spreadsheet(client, spreadsheet_id)
    dynamic_cfg = uploader.load_dynamic_config(spreadsheet, config_sheet_name)
    buzzvil_adgroup_id = dynamic_cfg.get("buzzvil_adgroup_id", "55015")

    results = {
        "date": yesterday,
        "rtb_app": None,
        "rtb_web": None,
        "buzzvil": None,
        "errors": [],
    }

    # ── RTB House 크롤링 ────────────────────────────────────
    logger.info("--- RTB House 크롤링 시작 ---")
    try:
        app_data, web_data = rtbhouse.scrape(
            app_url=static_cfg["rtbhouse"]["app_dashboard_url"],
            web_url=static_cfg["rtbhouse"]["web_dashboard_url"],
        )
        results["rtb_app"] = app_data
        results["rtb_web"] = web_data
        if not app_data:
            results["errors"].append("RTB_APP 데이터 없음")
        if not web_data:
            results["errors"].append("RTB_WEB 데이터 없음")
    except Exception as e:
        logger.error(f"RTB House 크롤링 실패: {e}")
        results["errors"].append(f"RTB House 오류: {e}")

    # ── Buzzvil 크롤링 ──────────────────────────────────────
    logger.info("--- Buzzvil 크롤링 시작 ---")
    try:
        bv_data = buzzvil.scrape(adgroup_id=buzzvil_adgroup_id)
        results["buzzvil"] = bv_data
        if not bv_data:
            results["errors"].append("Buzzvil 데이터 없음")
    except Exception as e:
        logger.error(f"Buzzvil 크롤링 실패: {e}")
        results["errors"].append(f"Buzzvil 오류: {e}")

    # ── Google Sheets 업로드 ────────────────────────────────
    logger.info("--- Google Sheets 업로드 시작 ---")
    try:
        uploaded_rows = uploader.append_daily_rows(
            spreadsheet_id=spreadsheet_id,
            data_sheet_name=data_sheet_name,
            config_sheet_name=config_sheet_name,
            rtb_app=results["rtb_app"],
            rtb_web=results["rtb_web"],
            buzzvil=results["buzzvil"],
        )
        results["uploaded_rows"] = uploaded_rows
        logger.info(f"업로드 완료: {len(uploaded_rows)}개 행")
    except Exception as e:
        logger.error(f"Google Sheets 업로드 실패: {e}")
        results["errors"].append(f"Sheets 업로드 오류: {e}")

    # ── 결과 요약 ────────────────────────────────────────────
    logger.info("=== 실행 완료 ===")
    if results["errors"]:
        logger.warning(f"경고/오류 항목: {results['errors']}")
    else:
        logger.info("모든 매체 정상 처리 완료")

    return results


if __name__ == "__main__":
    run()
