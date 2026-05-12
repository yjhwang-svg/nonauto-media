"""
RTB House 크롤러 — REST API 방식 (Selenium 불필요)

API: https://api.panel.rtbhouse.com/v5
인증: HTTP Basic Auth (RTBHOUSE_EMAIL / RTBHOUSE_PASSWORD)
광고주 해시: dashboard URL의 /dashboard/{hash}/ 부분
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

API_BASE = "https://api.panel.rtbhouse.com/v5"
TIMEOUT  = 60


def _get_credentials() -> tuple[str, str]:
    email    = os.environ.get("RTBHOUSE_EMAIL", "")
    password = os.environ.get("RTBHOUSE_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("RTBHOUSE_EMAIL 또는 RTBHOUSE_PASSWORD 환경변수가 없습니다.")
    return email, password


def _call_api(email: str, password: str, advertiser_hash: str, params: dict[str, Any]) -> list[dict]:
    url = f"{API_BASE}/advertisers/{advertiser_hash}/rtb-stats"
    logger.info(f"RTB API 호출: {url} | params={params}")

    resp = requests.get(
        url,
        params=params,
        auth=HTTPBasicAuth(email, password),
        timeout=TIMEOUT,
    )

    if not resp.ok:
        raise RuntimeError(f"RTB API 오류: {resp.status_code} {resp.text[:300]}")

    payload = resp.json()
    if payload.get("status") != "ok":
        raise RuntimeError(f"RTB API 응답 오류: {payload}")

    return payload.get("data", [])


def _extract_hash_from_url(dashboard_url: str) -> str:
    """
    'https://panel.rtbhouse.com/dashboard/zjgMiqEIsN3oQNMPG6hc?...'
    → 'zjgMiqEIsN3oQNMPG6hc'
    """
    path = dashboard_url.split("?")[0].rstrip("/")
    return path.split("/")[-1]


def fetch_day_totals(advertiser_hash: str, target_date: str, label: str) -> dict | None:
    """
    target_date: 'YYYY-MM-DD'
    returns: {"imps": int, "clicks": int, "cost": int} or None
    """
    try:
        email, password = _get_credentials()
        rows = _call_api(
            email=email,
            password=password,
            advertiser_hash=advertiser_hash,
            params={
                "dayFrom": target_date,
                "dayTo":   target_date,
                "groupBy": "day",
                "metrics": "impsCount-clicksCount-campaignCost",
            },
        )
        logger.info(f"[RTB {label}] API 응답 행 수: {len(rows)}")

        if not rows:
            logger.warning(f"[RTB {label}] {target_date} 데이터 없음")
            return None

        imps   = sum(int(float(r.get("impsCount",      0) or 0)) for r in rows)
        clicks = sum(int(float(r.get("clicksCount",    0) or 0)) for r in rows)
        cost   = sum(      float(r.get("campaignCost", 0) or 0)  for r in rows)

        result = {"imps": imps, "clicks": clicks, "cost": int(round(cost))}
        logger.info(f"[RTB {label}] 수집 완료 → {result}")
        return result

    except Exception as e:
        logger.error(f"[RTB {label}] 오류: {e}")
        return None


def scrape(app_url: str, web_url: str, target_date: str | None = None) -> tuple[dict | None, dict | None]:
    """
    RTB House APP / WEB 전일자 데이터를 API로 수집.
    target_date: 'YYYY-MM-DD' 형식, None이면 전일자 자동 계산
    """
    yesterday = target_date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info(f"RTB House API 크롤링 시작 | 대상 날짜: {yesterday}")

    app_hash = _extract_hash_from_url(app_url)
    web_hash = _extract_hash_from_url(web_url)

    app_data = fetch_day_totals(app_hash, yesterday, "APP")
    web_data = fetch_day_totals(web_hash, yesterday, "WEB")

    return app_data, web_data
