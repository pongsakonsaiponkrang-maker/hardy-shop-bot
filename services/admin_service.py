# ==========================================================
# HARDY ADMIN SERVICE - PRODUCTION
# - push context to admin
# - forward customer chat to admin
# - admin close order
# ==========================================================

from __future__ import annotations
from core.config import ADMIN_USER_IDS
from integrations.line_api import push_message
from services.order_service import update_order_status

def is_admin_uid(uid: str) -> bool:
    return uid in (ADMIN_USER_IDS or [])

def notify_admin_context(customer_uid: str, ctx: dict):
    """
    ส่ง context ล่าสุดให้แอดมิน (ถ้ามีข้อมูลสินค้า/ออเดอร์)
    """
    if not ADMIN_USER_IDS:
        return

    # สรุป context แบบอ่านง่าย
    lines = [
        "📣 ลูกค้าเรียกเจ้าหน้าที่ / หรือมีออเดอร์ใหม่",
        f"UID: {customer_uid}",
    ]

    if ctx:
        if ctx.get("order_id"):
            lines.append(f"ORDER ID: {ctx.get('order_id')}")
        if ctx.get("color") or ctx.get("size"):
            lines.append(f"สินค้า: {ctx.get('color')} / {ctx.get('size')}")
        if ctx.get("qty"):
            lines.append(f"จำนวน: {ctx.get('qty')}")
        if ctx.get("total") is not None:
            lines.append(f"ยอดรวม: {ctx.get('total')} บาท")
        if ctx.get("name"):
            lines.append(f"ชื่อผู้รับ: {ctx.get('name')}")
        if ctx.get("phone"):
            lines.append(f"เบอร์: {ctx.get('phone')}")
        if ctx.get("address"):
            lines.append(f"ที่อยู่: {ctx.get('address')}")
        if ctx.get("remain") is not None:
            lines.append(f"คงเหลือหลังตัดสต๊อก: {ctx.get('remain')}")

        if ctx.get("order_id"):
            lines.append("")
            lines.append("🧩 ปิดออเดอร์: พิมพ์")
            lines.append(f"CLOSE:{ctx.get('order_id')}")

    text = "\n".join(lines)

    for admin_uid in ADMIN_USER_IDS:
        push_message(admin_uid, text)

def forward_to_admin(customer_uid: str, message: str):
    if not ADMIN_USER_IDS:
        return
    text = f"💬 ข้อความจากลูกค้า\nUID: {customer_uid}\n\n{message}"
    for admin_uid in ADMIN_USER_IDS:
        push_message(admin_uid, text)

def admin_close_order(order_id: str) -> bool:
    return update_order_status(order_id, "CLOSED")
