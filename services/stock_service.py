from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional

from core.config import WS_STOCK, DEFAULT_PRICE_THB
from services.sheets_service import ensure_worksheet, get_all_records, find_first_row_index, update_cells

STOCK_HEADERS = ["color", "size", "stock", "price"]

def _ensure():
    ensure_worksheet(WS_STOCK, STOCK_HEADERS)

def _load() -> List[Dict[str, Any]]:
    _ensure()
    rows = get_all_records(WS_STOCK)
    # normalize
    out = []
    for r in rows:
        color = str(r.get("color") or "").strip()
        size = str(r.get("size") or "").strip()
        if not color or not size:
            continue
        stock = int(r.get("stock") or 0)
        price = int(r.get("price") or DEFAULT_PRICE_THB)
        out.append({"color": color, "size": size, "stock": stock, "price": price})
    return out

def get_available_colors() -> List[str]:
    rows = _load()
    colors = sorted({r["color"] for r in rows if r["stock"] > 0})
    return colors

def get_available_sizes(color: str) -> List[str]:
    color = str(color).strip()
    rows = _load()
    sizes = sorted({r["size"] for r in rows if r["color"] == color and r["stock"] > 0})
    return sizes

def get_stock(color: str, size: str) -> int:
    color = str(color).strip()
    size = str(size).strip()
    rows = _load()
    for r in rows:
        if r["color"] == color and r["size"] == size:
            return int(r["stock"])
    return 0

def get_price(color: str, size: str) -> int:
    color = str(color).strip()
    size = str(size).strip()
    rows = _load()
    for r in rows:
        if r["color"] == color and r["size"] == size:
            return int(r["price"])
    return DEFAULT_PRICE_THB

def deduct_stock(color: str, size: str, qty: int) -> Tuple[bool, int]:
    """
    Returns (ok, remain)
    """
    _ensure()
    color = str(color).strip()
    size = str(size).strip()
    qty = int(qty)

    # Find row by composite key "color|size" (we do manual scan)
    rows = get_all_records(WS_STOCK)
    for idx, r in enumerate(rows, start=2):  # row index in sheet
        if str(r.get("color")).strip() == color and str(r.get("size")).strip() == size:
            stock = int(r.get("stock") or 0)
            if qty <= 0:
                return False, stock
            if stock < qty:
                return False, stock
            remain = stock - qty
            update_cells(WS_STOCK, idx, {"stock": str(remain)})
            return True, remain

    return False, 0
