# ==========================================================
# STOCK SERVICE
# Manage stock + price from HARDY_STOCK sheet
# ==========================================================

from services.sheets_service import get_stock_sheet


# ==============================
# Get All Records
# ==============================
def _get_records():
    sheet = get_stock_sheet()
    return sheet.get_all_records()


# ==============================
# Available Colors (มี stock > 0)
# ==============================
def get_available_colors():
    records = _get_records()
    colors = set()

    for r in records:
        stock = int(r.get("stock", 0))
        if stock > 0:
            colors.add(r.get("color"))

    return list(colors)


# ==============================
# Available Sizes By Color
# ==============================
def get_available_sizes(color: str):
    records = _get_records()
    sizes = []

    for r in records:
        if r.get("color") == color and int(r.get("stock", 0)) > 0:
            sizes.append(r.get("size"))

    return sizes


# ==============================
# Get Stock
# ==============================
def get_stock(color: str, size: str):
    records = _get_records()

    for r in records:
        if r.get("color") == color and r.get("size") == size:
            return int(r.get("stock", 0))

    return 0


# ==============================
# Get Price
# ==============================
def get_price(color: str, size: str):
    records = _get_records()

    for r in records:
        if r.get("color") == color and r.get("size") == size:
            return int(r.get("price", 0))

    return 0


# ==============================
# Deduct Stock
# ==============================
def deduct_stock(color: str, size: str, qty: int):
    sheet = get_stock_sheet()
    records = sheet.get_all_values()

    header = records[0]
    col_color = header.index("color")
    col_size = header.index("size")
    col_stock = header.index("stock")

    for i in range(1, len(records)):
        row = records[i]

        if row[col_color] == color and row[col_size] == size:
            current = int(row[col_stock])
            if current < qty:
                return False, current

            new_stock = current - qty
            sheet.update_cell(i + 1, col_stock + 1, new_stock)
            return True, new_stock

    return False, 0
