from __future__ import annotations
from datetime import datetime, timezone, timedelta
import uuid
import re

BKK_TZ = timezone(timedelta(hours=7))

def now_iso() -> str:
    return datetime.now(tz=BKK_TZ).isoformat(timespec="seconds")

def gen_order_id() -> str:
    # HD + 10 chars
    return "HD" + uuid.uuid4().hex[:10].upper()

def gen_token() -> str:
    return uuid.uuid4().hex

def safe_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except Exception:
        return default

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))

def shorten_label(label: str, max_len: int = 20) -> str:
    label = re.sub(r"\s+", " ", (label or "").strip())
    return label[:max_len] if len(label) > max_len else label
