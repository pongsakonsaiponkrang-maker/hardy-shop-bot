from __future__ import annotations
from typing import Any, Dict, Optional

from core.config import WS_ORDER
from core.utils import now_iso, gen_order_id
from services.sheets_service import ensure_worksheet, get_all_records, append_row, find_first_row_index

ORDER_HEADERS = [
    "order_id",
    "uid",
    "confirm_token",   # idempotency key
    "color",
    "size",
    "qty",
    "price",
    "total",
    "status",
    "created_at",
]

def _ensure():
    ensure_worksheet(WS_ORDER, ORDER_HEADERS)

def find_order_by_confirm_token(confirm_token: str) -> Optional[str]:
    _ensure()
    confirm_token = str(confirm_token).strip()
    if not confirm_token:
        return None

    rows = get_all_records(WS_ORDER)
    for r in rows:
        if str(r.get("confirm_token")).strip() == confirm_token:
            return str(r.get("order_id")).strip() or None
    return None

def create_order(uid: str, data: Dict[str, Any]) -> str:
    """
    Idempotent create:
    - If confirm_token already exists -> return existing order_id
    - Else create new order row
    """
    _ensure()
    confirm_token = str(data.get("confirm_token") or "").strip()

    if confirm_token:
        existed = find_order_by_confirm_token(confirm_token)
        if existed:
            return existed

    order_id = gen_order_id()
    row = [
        order_id,
        uid,
        confirm_token,
        data.get("color", ""),
        data.get("size", ""),
        str(data.get("qty", "")),
        str(data.get("price", "")),
        str(data.get("total", "")),
        "NEW",
        now_iso(),
    ]
    append_row(WS_ORDER, row)
    return order_id
