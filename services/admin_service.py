from __future__ import annotations
from typing import Any, Dict, List

from core.config import ADMIN_USER_IDS
from integrations.line_api import push_message

def notify_admin_new_order(order_id: str, data: Dict[str, Any], remain: int):
    if not ADMIN_USER_IDS:
        return

    msg = (
        "🆕 NEW ORDER\n"
        f"ORDER ID: {order_id}\n"
        f"{data.get('color')} / {data.get('size')}\n"
        f"QTY: {data.get('qty')} | TOTAL: {data.get('total')}฿\n"
        f"Remain stock: {remain}"
    )

    for admin_uid in ADMIN_USER_IDS:
        push_message(admin_uid, [{"type": "text", "text": msg}])

def forward_to_admin(from_uid: str, text: str):
    if not ADMIN_USER_IDS:
        return

    text = (text or "").strip()
    if not text:
        return

    # simple anti-spam: limit length
    if len(text) > 500:
        text = text[:500] + "..."

    msg = f"💬 USER->ADMIN\nUID: {from_uid}\n{text}"
    for admin_uid in ADMIN_USER_IDS:
        push_message(admin_uid, [{"type": "text", "text": msg}])
