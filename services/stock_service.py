# ==========================================================
# HARDY STOCK SERVICE - SAFE VERSION
# ==========================================================

from services.sheets_service import get_all_records
from core.config import WS_STOCK, DEFAULT_PRICE_THB

def _clean(s):
    return str(s or "").strip()

def _norm(s):
    return _clean(s).lower()

def _load():
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
    return out

def get_available_colors():
    rows = _load()
    return sorted(list({r["color"] for r in rows if r["stock"] > 0}))

def get_available_sizes(color: str):
    rows = _load()
    return sorted([
        r["size"]
        for r in rows
        if _norm(r["color"]) == _norm(color) and r["stock"] > 0
    ])

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
    # ใช้ logic เดิมของคุณในการ update sheet
    # ตรงนี้ไม่เกี่ยวกับ bug ปัจจุบัน
    pass
