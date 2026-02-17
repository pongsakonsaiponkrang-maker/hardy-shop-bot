# ==========================================================
# HARDY STOCK SERVICE - WITH CACHE
# ==========================================================

import time
from services.sheets_service import get_all_records
from core.config import WS_STOCK, DEFAULT_PRICE_THB

_CACHE = {
    "data": [],
    "last_load": 0,
}

CACHE_TTL = 5  # seconds


def _clean(s):
    return str(s or "").strip()


def _norm(s):
    return _clean(s).lower()


def _load():
    now = time.time()

    # Use cache if not expired
    if now - _CACHE["last_load"] < CACHE_TTL:
        return _CACHE["data"]

    rows = get_all_records(WS_STOCK)
    out = []

    for r in rows:
        color = _clean(r.get("color"))
        size = _clean(r.get("size"))
        if not color or not size:
            continue

        stock = int(r.get("stock") or 0)
        price = int(r.get("price") or DEFAULT_PRICE_THB)

        out.append({
            "color": color,
            "size": size,
            "stock": stock,
            "price": price,
        })

    _CACHE["data"] = out
    _CACHE["last_load"] = now

    return out


def get_available_colors():
    rows = _load()
    return sorted({r["color"] for r in rows if r["stock"] > 0})


def get_available_sizes(color: str):
    rows = _load()
    return sorted(
        r["size"]
        for r in rows
        if _norm(r["color"]) == _norm(color) and r["stock"] > 0
    )


def get_stock(color: str, size: str):
    rows = _load()
    for r in rows:
        if _norm(r["color"]) == _norm(color) and _norm(r["size"]) == _norm(size):
            return r["stock"]
    return 0


def get_price(color: str, size: str):
    rows = _load()
    for r in rows:
        if _norm(r["color"]) == _norm(color) and _norm(r["size"]) == _norm(size):
            return r["price"]
    return DEFAULT_PRICE_THB


def deduct_stock(color: str, size: str, qty: int):
    # คุณใช้ logic เดิม update sheet
    # หลัง update เสร็จ ให้ reset cache
    _CACHE["last_load"] = 0
    return True, 0
