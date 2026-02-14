# services/stock_service.py

from typing import List, Dict, Tuple
from services.sheets_service import get_stock_sheet
from core.utils import safe_int
from core.config import LOW_STOCK_ALERT


# --------------------------------------------------
# INTERNAL
# --------------------------------------------------

def _get_all_records() -> List[Dict]:
    sheet = get_stock_sheet()
    return sheet.get_all_records()


def _get_header_index():
    sheet = get_stock_sheet()
    values = sheet.get_all_values()
    if not values:
        return None

    header = [h.strip() for h in values[0]]

    return {
        "color": header.index("color") + 1,
        "size": header.index("size") + 1,
        "stock": header.index("stock") + 1,
        "price": header.index("price") + 1,
        "header": header,
        "values": values,
    }


# --------------------------------------------------
# PUBLIC FUNCTIONS
# --------------------------------------------------

def get_all_colors(hide_out_of_stock: bool = True) -> List[str]:
    """
    Return unique colors
    If hide_out_of_stock=True -> only show colors that have stock > 0
    """
    records = _get_all_records()

    colors = set()

    for r in records:
        stock = safe_int(r.get("stock", 0))
        if hide_out_of_stock and stock <= 0:
            continue
        colors.add(r.get("color"))

    return sorted(list(colors))


def get_sizes_by_color(color: str, hide_out_of_stock: bool = True) -> List[str]:
    """
    Return sizes for a specific color
    """
    records = _get_all_records()

    sizes = []

    for r in records:
        if r.get("color") != color:
            continue

        stock = safe_int(r.get("stock", 0))
        if hide_out_of_stock and stock <= 0:
            continue

        sizes.append(r.get("size"))

    return sorted(sizes)


def get_stock(color: str, size: str) -> int:
    records = _get_all_records()

    for r in records:
        if r.get("color") == color and r.get("size") == size:
            return safe_int(r.get("stock", 0))

    return 0


def get_price(color: str, size: str) -> int:
    records = _get_all_records()

    for r in records:
        if r.get("color") == color and r.get("size") == size:
            return safe_int(r.get("price", 0))

    return 0


def deduct_stock(color: str, size: str, qty: int) -> Tuple[bool, int, bool]:
    """
    Deduct stock safely
    Return:
        (success, remaining_stock, is_low_stock)
    """
    idx = _get_header_index()
    if not idx:
        return False, 0, False

    sheet = get_stock_sheet()

    for i in range(2, len(idx["values"]) + 1):
        row = idx["values"][i - 1]

        c = row[idx["color"] - 1]
        s = row[idx["size"] - 1]

        if c == color and s == size:
            current = safe_int(row[idx["stock"] - 1])

            if current < qty:
                return False, current, False

            new_stock = current - qty

            sheet.update_cell(i, idx["stock"], new_stock)

            is_low = new_stock <= LOW_STOCK_ALERT

            return True, new_stock, is_low

    return False, 0, False