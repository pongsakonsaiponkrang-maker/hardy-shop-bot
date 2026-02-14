# services/admin_service.py

from typing import Dict, List, Optional
from core.config import ADMIN_USER_IDS, LOW_STOCK_ALERT
from core.utils import now_str
from integrations.line_api import push_message, text_message, quick_reply_message


def _send_to_admins(messages: List[Dict]) -> None:
    if not ADMIN_USER_IDS:
        return
    for admin_uid in ADMIN_USER_IDS:
        try:
            push_message(admin_uid, messages)
        except Exception:
            continue


def notify_new_order(order_id: str, data: Dict, remaining_stock: int) -> None:
    qty = int(data["qty"])
    price = int(data["price"])
    amount = qty * price

    text = (
        "🔥 NEW ORDER (HARDY)\n\n"
        f"ORDER ID: {order_id}\n"
        f"เวลา: {now_str()}\n\n"
        f"ชื่อ: {data['name']}\n"
        f"เบอร์: {data['phone']}\n"
        f"ที่อยู่: {data['address']}\n\n"
        f"สินค้า: HARDY Utility Chino\n"
        f"สี: {data['color']} | ไซส์: {data['size']}\n"
        f"จำนวน: {qty}\n"
        f"ราคา/ตัว: {price:,} บาท\n"
        f"ยอดรวม: {amount:,} บาท\n\n"
        f"สต๊อกคงเหลือ: {remaining_stock}"
    )

    _send_to_admins([text_message(text)])

    if remaining_stock <= LOW_STOCK_ALERT:
        _send_to_admins([text_message(f"⚠ STOCK LOW: {data['color']} {data['size']} เหลือ {remaining_stock}")])


def forward_customer_message(customer_uid: str, customer_text: str) -> None:
    """
    ส่งข้อความลูกค้าไปหาแอดมิน พร้อมปุ่มให้แอดมินกด 'ตอบคนนี้'
    """
    msg = quick_reply_message(
        f"📩 ลูกค้าส่งข้อความ\nUID: {customer_uid}\n\n{customer_text}",
        [
            ("ตอบคนนี้", f"ADMIN_REPLY_TO:{customer_uid}"),
            ("จบแชทคนนี้", f"ADMIN_END_CHAT:{customer_uid}"),
        ],
    )
    _send_to_admins([msg])


def admin_help_message() -> Dict:
    return quick_reply_message(
        "🛠 ADMIN COMMAND\nกดปุ่มเพื่อใช้งาน",
        [
            ("ดูคู่มือ", "ADMIN_HELP"),
        ],
    )