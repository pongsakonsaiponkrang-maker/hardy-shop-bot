# ==========================================================
# ADMIN SERVICE
# Handle admin notification + admin chat mode
# ==========================================================

from integrations.line_api import push_message
from core.config import ADMIN_USER_IDS
from core.utils import now_str


# ==============================
# Notify Admin: New Order
# ==============================
def notify_admin_new_order(order_id: str, data: dict, remaining_stock: int):
    """
    แจ้งเตือน admin เมื่อมีออเดอร์ใหม่
    """

    qty = int(data["qty"])
    price = int(data["price"])
    amount = qty * price

    message = (
        "🔥 NEW ORDER (HARDY)\n\n"
        f"ORDER ID: {order_id}\n"
        f"ชื่อ: {data['name']}\n"
        f"เบอร์: {data['phone']}\n"
        f"ที่อยู่: {data['address']}\n\n"
        f"สินค้า: HARDY Utility Chino\n"
        f"สี: {data['color']} | ไซส์: {data['size']} | จำนวน: {qty}\n"
        f"ราคา/ตัว: {price:,} บาท\n"
        f"ยอดรวม: {amount:,} บาท\n"
        f"คงเหลือสต๊อก: {remaining_stock}\n\n"
        f"เวลา: {now_str()}"
    )

    for admin_id in ADMIN_USER_IDS:
        try:
            push_message(admin_id, message)
        except Exception:
            pass


# ==============================
# Notify Admin: Low Stock
# ==============================
def notify_low_stock(color: str, size: str, remaining_stock: int):
    if remaining_stock > 3:
        return

    warn = f"⚠ STOCK LOW: {color} {size} เหลือ {remaining_stock}"

    for admin_id in ADMIN_USER_IDS:
        try:
            push_message(admin_id, warn)
        except Exception:
            pass
