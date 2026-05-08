"""
Google Sheets 연동 모듈
- 서비스 계정 인증
- '수기매체업로드' 시트에 행 추가
- '설정' 시트에서 동적 설정값(BSA 비용, Buzzvil adgroup_id) 읽기/쓰기
"""

import json
import logging
import os

import gspread
from google.oauth2.service_account import Credentials

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# '설정' 시트 초기값 (처음 시트 생성 시 사용)
DEFAULT_CONFIG = {
    "buzzvil_adgroup_id": "55015",
    "bsa_mobile_cost": "920000",
    "bsa_pc_cost": "460000",
}


def _get_credentials() -> Credentials:
    """환경변수 GOOGLE_SERVICE_ACCOUNT (JSON 문자열)에서 인증 정보 로드."""
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT", "")
    if not sa_json:
        raise ValueError("환경변수 GOOGLE_SERVICE_ACCOUNT가 설정되지 않았습니다.")
    sa_info = json.loads(sa_json)
    return Credentials.from_service_account_info(sa_info, scopes=SCOPES)


def get_client() -> gspread.Client:
    creds = _get_credentials()
    return gspread.authorize(creds)


def get_spreadsheet(client: gspread.Client, spreadsheet_id: str) -> gspread.Spreadsheet:
    return client.open_by_key(spreadsheet_id)


# ─── 설정 시트 ─────────────────────────────────────────────────────────────────

def _ensure_config_sheet(spreadsheet: gspread.Spreadsheet, sheet_name: str):
    """'설정' 시트가 없으면 생성하고 기본값을 채운다."""
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        logger.info(f"'{sheet_name}' 시트 없음 → 새로 생성")
        ws = spreadsheet.add_worksheet(title=sheet_name, rows=20, cols=2)
        ws.update("A1:B1", [["key", "value"]])
        rows = [[k, v] for k, v in DEFAULT_CONFIG.items()]
        ws.append_rows(rows)
        return ws


def load_dynamic_config(spreadsheet: gspread.Spreadsheet, sheet_name: str) -> dict:
    """
    '설정' 시트에서 key-value 쌍을 읽어 dict로 반환.
    예: {"buzzvil_adgroup_id": "55015", "bsa_mobile_cost": "920000", ...}
    """
    ws = _ensure_config_sheet(spreadsheet, sheet_name)
    records = ws.get_all_records()
    config = {row["key"]: row["value"] for row in records if row.get("key")}
    # 누락된 키는 기본값으로 채움
    for k, v in DEFAULT_CONFIG.items():
        config.setdefault(k, v)
    logger.info(f"동적 설정 로드: {config}")
    return config


def save_dynamic_config(spreadsheet: gspread.Spreadsheet, sheet_name: str, updates: dict):
    """
    '설정' 시트의 특정 key 값을 업데이트.
    updates: {"buzzvil_adgroup_id": "55016", ...}
    """
    ws = _ensure_config_sheet(spreadsheet, sheet_name)
    records = ws.get_all_records()
    key_to_row = {row["key"]: idx + 2 for idx, row in enumerate(records)}  # 1-indexed, +1 for header

    for key, value in updates.items():
        if key in key_to_row:
            ws.update_cell(key_to_row[key], 2, str(value))
            logger.info(f"설정 업데이트: {key} = {value}")
        else:
            ws.append_row([key, str(value)])
            logger.info(f"설정 추가: {key} = {value}")


# ─── 데이터 업로드 ─────────────────────────────────────────────────────────────

def _build_rows(yesterday: str, dynamic_config: dict,
                rtb_app: dict | None, rtb_web: dict | None,
                buzzvil: dict | None) -> list[list]:
    """
    5개 행을 구성.
    컬럼 순서: 날짜 | 매체구분 | 미디어 | 디바이스 | 소재명 | 노출 | 클릭 | 비용
    """
    mobile_cost = int(dynamic_config.get("bsa_mobile_cost", 920000))
    pc_cost     = int(dynamic_config.get("bsa_pc_cost",     460000))

    def safe(data: dict | None, key: str, fallback=0):
        return data[key] if data else fallback

    rows = [
        # BSA Mobile
        [yesterday, "BSA", "BSA", "Mobile", "홈링크.링크", 0, 0, mobile_cost],
        # BSA PC
        [yesterday, "BSA", "BSA", "PC",     "홈링크.링크", 0, 0, pc_cost],
        # RTB APP
        [yesterday, "RTB_APP", "RT", "없음", "없음",
         safe(rtb_app, "imps"), safe(rtb_app, "clicks"), safe(rtb_app, "cost")],
        # RTB WEB
        [yesterday, "RTB_WEB", "RT", "없음", "없음",
         safe(rtb_web, "imps"), safe(rtb_web, "clicks"), safe(rtb_web, "cost")],
        # 버즈빌
        [yesterday, "버즈빌", "RT", "없음", "없음",
         safe(buzzvil, "imps"), safe(buzzvil, "clicks"), safe(buzzvil, "cost")],
    ]
    return rows


def append_daily_rows(spreadsheet_id: str, data_sheet_name: str, config_sheet_name: str,
                      rtb_app: dict | None, rtb_web: dict | None, buzzvil: dict | None,
                      target_date: str | None = None):
    """
    수기매체업로드 시트 맨 아래에 전일자 5개 행을 추가.
    """
    target_date = target_date or get_target_date()
    logger.info(f"Google Sheets 업로드 시작 (날짜: {target_date})")

    client = get_client()
    spreadsheet = get_spreadsheet(client, spreadsheet_id)
    dynamic_config = load_dynamic_config(spreadsheet, config_sheet_name)

    rows = _build_rows(target_date, dynamic_config, rtb_app, rtb_web, buzzvil)

    data_ws = spreadsheet.worksheet(data_sheet_name)
    data_ws.append_rows(rows, value_input_option="USER_ENTERED")

    logger.info(f"업로드 완료: {len(rows)}개 행 추가 (날짜: {target_date})")
    return rows
