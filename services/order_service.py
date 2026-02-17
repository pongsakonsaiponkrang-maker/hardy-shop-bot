# ==========================================================
# HARDY ORDER SERVICE - CLEAN VERSION
# Compatible with new sheets_service
# ==========================================================

from core.config import WS_ORDER
from core.utils import gen_order_id, now_iso
from services.sheets_service import (
    append_row,
    get_all_records,
    find_row_by_value,
    update_row,
)


# ==========================================================
# CREATE ORDER
# ==========================================================

def create_order(uid: str, data: dict) -> str:
    """
    Create new order (simple version)
    """

    order_id = gen_order_id()

    row = [
        order_id,                     # order_id
        uid,                          # uid
        data.get("confirm_token", ""), # confirm_token
        data.get("color", ""),         # color
        data.get("size", ""),          # size
        data.get("qty", ""),           # qty
        data.get("price", ""),         # price
        data.get("total", ""),         # total
        data.get("name", ""),          # name
        data.get("phone", ""),         # phone
        data.get("address", ""),       # address
        data.get("payment_status", "PENDING"),  # payment_status
        "NEW",                         # status
        now_iso(),                     # created_at
    ]

    append_row(WS_ORDER, row)

    return order_id


# ==========================================================
# FIND ORDER BY ID
# ==========================================================

def get_order(order_id: str):
    rows = get_all_records(WS_ORDER)

    for r in rows:
        if str(r.get("order_id")).strip() == str(order_id).strip():
            return r

    return None


# ==========================================================
# UPDATE ORDER STATUS
# ==========================================================

def update_order_status(order_id: str, new_status: str):
    row_index = find_row_by_value(WS_ORDER, "order_id", order_id)
    if not row_index:
        return False

    rows = get_all_records(WS_ORDER)
    target = None

    for r in rows:
        if str(r.get("order_id")).strip() == str(order_id).strip():
            target = r
            break

    if not target:
        return False

    updated_row = [
        target.get("order_id"),
        target.get("uid"),
        target.get("confirm_token"),
        target.get("color"),
        target.get("size"),
        target.get("qty"),
        target.get("price"),
        target.get("total"),
        target.get("name"),
        target.get("phone"),
        target.get("address"),
        target.get("payment_status"),
        new_status,
        target.get("created_at"),
    ]

    update_row(WS_ORDER, row_index, updated_row)

    return True
