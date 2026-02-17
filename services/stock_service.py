# ==========================================================
# HARDY STOCK SERVICE - FIXED VERSION
# ลดสต๊อกจริง
# ==========================================================

from core.config import WS_STOCK
from services.sheets_service import get_ws


def _normalize(s):
    return str(s).strip()


def get_available_colors():
    ws = get_ws(WS_STOCK)
    rows = ws.get_all_values()[1:]

    colors = set()
    for r in rows:
        if r and int(r[2]) > 0:
            colors.add(_normalize(r[0]))

    return sorted(list(colors))


def get_available_sizes(color):
    ws = get_ws(WS_STOCK)
    rows = ws.get_all_values()[1:]

    sizes = []
    for r in rows:
        if _normalize(r[0]) == _normalize(color) and int(r[2]) > 0:
            sizes.append(_normalize(r[1]))

    return sizes


def get_stock(color, size):
    ws = get_ws(WS_STOCK)
    rows = ws.get_all_values()[1:]

    for r in rows:
        if _normalize(r[0]) == _normalize(color) and _normalize(r[1]) == _normalize(size):
            return int(r[2])

    return 0


def get_price(color, size):
    ws = get_ws(WS_STOCK)
    rows = ws.get_all_values()[1:]

    for r in rows:
        if _normalize(r[0]) == _normalize(color) and _normalize(r[1]) == _normalize(size):
            return int(r[3])

    return 0


def deduct_stock(color, size, qty):
    ws = get_ws(WS_STOCK)
    rows = ws.get_all_values()

    for idx, r in enumerate(rows[1:], start=2):

        if (
            _normalize(r[0]) == _normalize(color)
            and _normalize(r[1]) == _normalize(size)
        ):
            current_stock = int(r[2])

            if current_stock < qty:
                return False, current_stock

            new_stock = current_stock - qty

            # update stock column (C)
            ws.update(f"C{idx}", [[new_stock]])

            return True, new_stock

    return False, 0
