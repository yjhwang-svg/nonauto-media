import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
TARGET_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def get_target_date(now: datetime | None = None) -> str:
    override = os.environ.get("TARGET_DATE")
    if override:
        if not TARGET_DATE_RE.match(override):
            raise ValueError("TARGET_DATE는 YYYY-MM-DD 형식이어야 합니다.")
        return override

    current = now or datetime.now(KST)
    if current.tzinfo is None:
        current = current.replace(tzinfo=KST)

    return (current.astimezone(KST).date() - timedelta(days=1)).isoformat()
