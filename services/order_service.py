# services/order_service.py

from typing import Dict
from core.utils import now_str
from services.sheets_service import get_orders_sheet


def generate_order_id() -> str:
    """
    Generate unique order ID
    Example: HD1700000000
    """
    import time
    return f"HD{int(time.time())}"


def calculate_amount(qty: int, price: int) -> int:
    """
    Calculate total amount
    """
    return int(qty) * int(price)


def create_order(data: Dict) -> str:
    """
    Create order in HARDY_ORDER sheet

    Required keys in data:
    - user_id
    - name
    - phone
    - address
    - color
    - size
    - qty
    - price
    """

    sheet = get_orders_sheet()

    order_id = generate_order_id()

    qty = int(data["qty"])
    price = int(data["price"])
    amount = calculate_amount(qty, price)

    sheet.append_row([
        now_str(),               # time
        order_id,                # order_id
        data["user_id"],         # user_id
        data["name"],            # name
        data["phone"],           # phone
        data["address"],         # address
        data["color"],           # color
        data["size"],            # size
        qty,                     # qty
        amount,                  # total amount
        "NEW",                   # status
    ])

    return order_id