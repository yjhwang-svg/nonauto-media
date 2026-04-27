"""
수기 매체 자동화 대시보드
- 수동 실행 (GitHub Actions workflow_dispatch 호출)
- 설정 관리 (Buzzvil adgroup_id, BSA 비용)
- 최근 업로드 데이터 확인

Streamlit Community Cloud 배포 시 secrets.toml 필요:
  GOOGLE_SERVICE_ACCOUNT = '{"type": "service_account", ...}'
  GITHUB_TOKEN = "ghp_xxxx"         # repo + workflow 권한 필요
  GITHUB_REPO  = "yjhwang-svg/nonauto-media"
"""

import json
import os
import time

import requests
import streamlit as st

# ─── 페이지 설정 ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="수기매체 자동화",
    page_icon="📊",
    layout="wide",
)

# ─── 환경변수 / Streamlit Secrets 로드 ──────────────────────────────────────────
def get_secret(key: str, default: str = "") -> str:
    """Streamlit secrets → 환경변수 순으로 조회."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.environ.get(key, default)


GOOGLE_SA_JSON  = get_secret("GOOGLE_SERVICE_ACCOUNT")
GITHUB_TOKEN    = get_secret("GITHUB_TOKEN")
GITHUB_REPO     = get_secret("GITHUB_REPO", "yjhwang-svg/nonauto-media")
SPREADSHEET_ID  = "18Gzpi_yeYQXbjqChlhm9EHT7z0Gi-65D0NCX7iC3SJ4"
DATA_SHEET      = "수기매체업로드"
CONFIG_SHEET    = "설정"


# ─── Google Sheets 클라이언트 (캐시) ────────────────────────────────────────────
@st.cache_resource
def _get_sheets_client():
    if not GOOGLE_SA_JSON:
        return None
    import gspread
    from google.oauth2.service_account import Credentials

    sa_info = json.loads(GOOGLE_SA_JSON)
    creds = Credentials.from_service_account_info(
        sa_info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds)


def get_spreadsheet():
    client = _get_sheets_client()
    if not client:
        return None
    return client.open_by_key(SPREADSHEET_ID)


# ─── 설정 읽기/쓰기 ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return {"buzzvil_adgroup_id": "55015", "bsa_mobile_cost": "920000", "bsa_pc_cost": "460000"}
    try:
        ws = spreadsheet.worksheet(CONFIG_SHEET)
        records = ws.get_all_records()
        return {row["key"]: row["value"] for row in records if row.get("key")}
    except Exception as e:
        st.warning(f"설정 시트 로드 실패: {e}")
        return {}


def save_config(updates: dict):
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        st.error("Google Sheets 연결 안됨")
        return
    try:
        ws = spreadsheet.worksheet(CONFIG_SHEET)
        records = ws.get_all_records()
        key_to_row = {row["key"]: idx + 2 for idx, row in enumerate(records)}
        for key, value in updates.items():
            if key in key_to_row:
                ws.update_cell(key_to_row[key], 2, str(value))
            else:
                ws.append_row([key, str(value)])
    except Exception as e:
        st.error(f"설정 저장 실패: {e}")


# ─── 최근 데이터 읽기 ───────────────────────────────────────────────────────────
def load_recent_data(n: int = 20) -> list[list]:
    spreadsheet = get_spreadsheet()
    if not spreadsheet:
        return []
    try:
        ws = spreadsheet.worksheet(DATA_SHEET)
        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return []
        header = all_values[0]
        recent = all_values[max(1, len(all_values) - n):]
        return [header] + recent
    except Exception as e:
        st.warning(f"데이터 로드 실패: {e}")
        return []


# ─── GitHub Actions 수동 트리거 ─────────────────────────────────────────────────
def trigger_github_action() -> tuple[bool, str]:
    if not GITHUB_TOKEN:
        return False, "GITHUB_TOKEN이 설정되지 않았습니다. Streamlit Secrets를 확인하세요."
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/daily_crawl.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"ref": "main"}
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    if resp.status_code == 204:
        return True, "GitHub Actions 워크플로우가 시작됐습니다. 약 3~5분 후 완료됩니다."
    return False, f"트리거 실패 (HTTP {resp.status_code}): {resp.text}"


# ─── UI 구성 ────────────────────────────────────────────────────────────────────
st.title("📊 수기매체 자동화 대시보드")
st.caption("RTB House(APP/WEB) · Buzzvil · BSA 데이터를 매일 자동 수집하여 Google Sheets에 업로드합니다.")

tab_run, tab_config, tab_data = st.tabs(["▶ 수동 실행", "⚙ 설정 관리", "📋 최근 데이터"])


# ── 탭 1: 수동 실행 ─────────────────────────────────────────────────────────────
with tab_run:
    st.subheader("지금 바로 실행")
    st.info(
        "버튼을 누르면 GitHub Actions에서 크롤링이 즉시 시작됩니다.  \n"
        "완료까지 약 **3~5분** 소요됩니다."
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🚀 지금 실행", type="primary", use_container_width=True):
            with st.spinner("GitHub Actions 트리거 중..."):
                success, message = trigger_github_action()
            if success:
                st.success(message)
            else:
                st.error(message)

    st.divider()
    st.subheader("최근 실행 이력")
    st.caption("GitHub Actions 탭에서 상세 로그를 확인할 수 있습니다.")

    if GITHUB_TOKEN:
        runs_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/daily_crawl.yml/runs?per_page=5"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        }
        try:
            resp = requests.get(runs_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                runs = resp.json().get("workflow_runs", [])
                for run in runs:
                    status_icon = {"success": "✅", "failure": "❌", "in_progress": "🔄"}.get(
                        run["conclusion"] or run["status"], "⏳"
                    )
                    st.write(
                        f"{status_icon} `{run['created_at'][:16]}` — "
                        f"[{run['display_title']}]({run['html_url']})"
                    )
        except Exception as e:
            st.warning(f"실행 이력 로드 실패: {e}")
    else:
        st.warning("GITHUB_TOKEN 설정 후 실행 이력을 확인할 수 있습니다.")


# ── 탭 2: 설정 관리 ─────────────────────────────────────────────────────────────
with tab_config:
    st.subheader("동적 설정값 관리")
    st.caption("변경 후 저장하면 다음 실행부터 즉시 반영됩니다.")

    cfg = load_config()

    with st.form("config_form"):
        st.markdown("**Buzzvil**")
        adgroup_id = st.text_input(
            "Adgroup ID (매월 변경)",
            value=cfg.get("buzzvil_adgroup_id", "55015"),
            help="URL의 /adgroups/{숫자}/report 에서 숫자 부분",
        )

        st.markdown("**BSA 비용 (원)**")
        col_m, col_p = st.columns(2)
        with col_m:
            mobile_cost = st.number_input(
                "Mobile 비용",
                value=int(cfg.get("bsa_mobile_cost", 920000)),
                step=10000,
            )
        with col_p:
            pc_cost = st.number_input(
                "PC 비용",
                value=int(cfg.get("bsa_pc_cost", 460000)),
                step=10000,
            )

        submitted = st.form_submit_button("💾 저장", type="primary")
        if submitted:
            save_config({
                "buzzvil_adgroup_id": adgroup_id,
                "bsa_mobile_cost": str(mobile_cost),
                "bsa_pc_cost": str(pc_cost),
            })
            st.success("설정이 저장됐습니다. ✅")
            st.cache_resource.clear()


# ── 탭 3: 최근 데이터 ────────────────────────────────────────────────────────────
with tab_data:
    st.subheader("최근 업로드 데이터 (최근 20행)")

    if st.button("🔄 새로고침"):
        st.cache_resource.clear()

    rows = load_recent_data(20)
    if rows and len(rows) > 1:
        import pandas as pd
        header = rows[0]
        data   = rows[1:]
        df = pd.DataFrame(data, columns=header)
        st.dataframe(df, use_container_width=True, hide_index=True)
    elif rows:
        st.info("데이터가 없습니다.")
    else:
        st.warning("Google Sheets 연결을 확인하세요.")
