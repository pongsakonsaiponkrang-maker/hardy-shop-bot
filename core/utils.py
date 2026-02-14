# core/utils.py

import time
from datetime import datetime, timezone, timedelta
from typing import Any

APP_TZ = timezone(timedelta(hours=7))


def now_str() -> str:
    """
    Current datetime string in Thailand timezone
    """
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")


def now_ts() -> int:
    """
    Current Unix timestamp
    """
    return int(time.time())


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safe convert to int
    """
    try:
        return int(str(value).strip())
    except Exception:
        return default


def is_empty(value: Any) -> bool:
    return value is None or str(value).strip() == ""