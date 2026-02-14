# ==========================================================
# HARDY - STOCK SERVICE
# Handles:
# - Get available colors
# - Get available sizes per color
# - Get stock
# - Get price
# - Deduct stock safely
# ==========================================================

from typing import Dict, List, Tuple, Any
from services.sheets_service import get_stock_sheet
from core.utils import safe_int


# ----------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------

def _get_header_map(values: List[List[str]]) -> Dict[str, int]:
    """
    Map header name -> column index
    Expected headers: color, size, stock, price
    """
    header = [h.strip().lower() for h in values[0]]
    return {name: header.index(name) for name in header}


def _get_all_rows():
    sheet = get_stock_sheet()
    values = sheet.get_all_values()
    if not values or len(values) < 2:
        return [], {}

    header_map = _get_header_map(values)
    rows = values[1:]  # skip header
    return rows, header_map


# ----------------------------------------------------------
# Public API
# ----------------------------------------------------------

def get_available_colors() -> List[str]:
    """
    Return only colors that have stock > 0
    """
    rows, header = _get_all_rows()
    colors = set()

    for row in rows:
        try:
            stock = safe_int(row[header["stock"]])
            if stock > 0:
                colors.add(row[header["color"]])
        except Exception:
            continue

    return sorted(list(colors))


def get_available_sizes(color: str) -> List[str]:
    """
    Return sizes with stock > 0 for given color
    """
    rows, header = _get_all_rows()
    sizes = []

    for row in rows:
        try:
            if row[header["color"]] != color:
                continue

            stock = safe_int(row[header["stock"]])
            if stock > 0:
                sizes.append(row[header["size"]])
        except Exception:
            continue

    return sizes


def get_stock(color: str, size: str) -> int:
    rows, header = _get_all_rows()

    for row in rows:
        try:
            if (
                row[header["color"]] == color and
                row[header["size"]] == size
            ):
                return safe_int(row[header["stock"]])
        except Exception:
            continue

    return 0


def get_price(color: str, size: str) -> int:
    rows, header = _get_all_rows()

    for row in rows:
        try:
            if (
                row[header["color"]] == color and
                row[header["size"]] == size
            ):
                return safe_int(row[header["price"]])
        except Exception:
            continue

    return 0


def deduct_stock(color: str, size: str, qty: int) -> Tuple[bool, int]:
    """
    Safely deduct stock.
    Return: (success, remaining_stock)
    """
    sheet = get_stock_sheet()
    values = sheet.get_all_values()

    if not values or len(values) < 2:
        return False, 0

    header = _get_header_map(values)

    for i in range(1, len(values)):  # start from row 2
        row = values[i]

        try:
            if (
                row[header["color"]] == color and
                row[header["size"]] == size
            ):
                current = safe_int(row[header["stock"]])

                if qty <= 0 or current < qty:
                    return False, current

                new_stock = current - qty

                # update sheet (row index +1 because sheet index starts at 1)
                sheet.update_cell(
                    i + 1,
                    header["stock"] + 1,
                    new_stock
                )

                return True, new_stock

        except Exception:
            continue

    return False, 0
