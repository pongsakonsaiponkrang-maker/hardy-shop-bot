# ==========================================================
# HARDY ORDER FLOW - V3.2 PRODUCTION SAFE
# Confirm 2-step (A) + Collect Name/Phone/Address
# Final Confirm: ONLY ONE BUTTON (no cancel)
# Idempotent + confirm_lock + token
# parse_payload() / quickReply limit + fallback
# ==========================================================

from __future__ import annotations
from typing import List, Tuple, Dict, Any

from integrations.line_api import reply_message
from services.stock_service import (
    get_available_colors,
    get_available_sizes,
    get_stock,
    get_price,
    deduct_stock,
)
from services.session_service import (
    get_session,
    set_session,
    clear_session,
)
from core.config import QUICK_REPLY_LIMIT
from core.utils import shorten_label, safe_int, gen_token

# ----------------------------------------------------------
# Payload Helper
# ----------------------------------------------------------

def parse_payload(text: str) -> Tuple[str, List[str]]:
    t = (text or "").strip()
    if not t.startswith("BOT:"):
        return "", []
    parts = t.split(":")
    if len(parts) < 2:
        return "", []
    return parts[0], parts[1:]  # ("BOT", [...])

# ----------------------------------------------------------
# Quick Reply builder with limit + fallback
# ----------------------------------------------------------

def quick(text: str, buttons: List[Tuple[str, str]]) -> Dict[str, Any]:
    buttons = (buttons or [])[:QUICK_REPLY_LIMIT]
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": shorten_label(label, 20),
                        "text": payload,
                    },
                }
                for label, payload in buttons
            ]
        },
    }

def build_quick_or_fallback(text: str, buttons: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    buttons = buttons or []
    if len(buttons) <= QUICK_REPLY_LIMIT:
        return [quick(text, buttons)]

    lines = [text, ""]
    for i, (label, _) in enumerate(buttons, start=1):
        lines.append(f"{i}. {label}")
    fallback_text = "\n".join(lines).strip()

    limited = buttons[:QUICK_REPLY_LIMIT]
    return [
        {"type": "text", "text": fallback_text},
        quick("เลือกจากปุ่มด้านล่าง (แสดงบางส่วน):", limited),
    ]

# ----------------------------------------------------------
# Menu
# ----------------------------------------------------------

def send_menu(reply_token: str):
    reply_message(
        reply_token,
        build_quick_or_fallback(
            "👖 HARDY\nเลือกเมนู:",
            [
                ("🛒 สั่งซื้อ", "BOT:ORDER"),
                ("🎨 ดูสี", "BOT:COLORS"),
                ("💬 คุยกับแอดมิน", "BOT:ADMIN"),
            ],
        ),
    )

# ----------------------------------------------------------
# State guard
# ----------------------------------------------------------

def require_state(uid: str, reply_token: str, expected_state: str) -> bool:
    session = get_session(uid) or {}
    if session.get("state") != expected_state:
        send_menu(reply_token)
        return False
    return True

# ----------------------------------------------------------
# Validators
# ----------------------------------------------------------

def is_valid_phone_10(s: str) -> bool:
    s = (s or "").strip().replace("-", "").replace(" ", "")
    return len(s) == 10 and s.isdigit() and s.startswith("0")

def is_valid_name(s: str) -> bool:
    s = (s or "").strip()
    return len(s) >= 3

def is_valid_address(s: str) -> bool:
    s = (s or "").strip()
    return len(s) >= 10

# ----------------------------------------------------------
# Main flow
# ----------------------------------------------------------

def handle(uid: str, reply_token: str, text: str):
    session = get_session(uid) or {}
    state = session.get("state", "IDLE")
    data = session.get("data", {}) or {}

    plain = (text or "").strip()

    # Global reset/menu
    if plain.lower() in ["เมนู", "menu", "hi", "hello", "start"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    cmd, parts = parse_payload(plain)

    # COLORS
    if cmd == "BOT" and parts[:1] == ["COLORS"]:
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return
        reply_message(reply_token, [{"type": "text", "text": "🎨 สีที่มี: " + ", ".join(colors)}])
        send_menu(reply_token)
        return

    # START ORDER
    if cmd == "BOT" and parts[:1] == ["ORDER"]:
        clear_session(uid)
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]
        reply_message(reply_token, build_quick_or_fallback("เลือกสี:", buttons))
        set_session(uid, "WAIT_COLOR", {})
        return

    # COLOR
    if cmd == "BOT" and parts[:1] == ["COLOR"]:
        if not require_state(uid, reply_token, "WAIT_COLOR"):
            return
        if len(parts) != 2:
            send_menu(reply_token)
            return

        color = parts[1].strip()
        sizes = get_available_sizes(color)
        if not sizes:
            reply_message(reply_token, [{"type": "text", "text": "สีนี้หมด ❌"}])
            return

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            buttons.append((f"{s} | {price}฿ | {stock}", f"BOT:SIZE:{color}:{s}"))

        reply_message(reply_token, build_quick_or_fallback(f"สี {color}\nเลือกไซส์:", buttons))
        set_session(uid, "WAIT_SIZE", {"color": color})
        return

    # SIZE
    if cmd == "BOT" and parts[:1] == ["SIZE"]:
        if not require_state(uid, reply_token, "WAIT_SIZE"):
            return
        if len(parts) != 3:
            send_menu(reply_token)
            return

        color, size = parts[1].strip(), parts[2].strip()
        if data.get("color") != color:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        price = get_price(color, size)
        if stock <= 0:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกหมด ❌"}])
            return

        max_btn = min(stock, 5)
        buttons = [(str(n), f"BOT:QTY:{color}:{size}:{n}") for n in range(1, max_btn + 1)]
        reply_message(reply_token, build_quick_or_fallback(
            f"{color} / {size}\nราคา {price} บาท\nเลือกจำนวน:",
            buttons,
        ))
        set_session(uid, "WAIT_QTY", {"color": color, "size": size})
        return

    # QTY -> item summary confirm (confirm step 1)
    if cmd == "BOT" and parts[:1] == ["QTY"]:
        if not require_state(uid, reply_token, "WAIT_QTY"):
            return
        if len(parts) != 4:
            send_menu(reply_token)
            return

        color, size, qty_str = parts[1].strip(), parts[2].strip(), parts[3].strip()
        if data.get("color") != color or data.get("size") != size:
            send_menu(reply_token)
            return

        qty = safe_int(qty_str, 0)
        if qty <= 0:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        if qty > stock:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        price = get_price(color, size)
        total = qty * price

        set_session(
            uid,
            "WAIT_CONFIRM_ITEM",
            {
                "color": color,
                "size": size,
                "qty": qty,
                "price": price,
                "total": total,
            },
        )

        reply_message(
            reply_token,
            build_quick_or_fallback(
                f"🧾 สรุปสินค้า\n{color} / {size}\n{qty} ตัว\nรวม {total} บาท\n\nยืนยันสินค้าเพื่อกรอกข้อมูลจัดส่ง",
                [
                    ("✅ ยืนยันสินค้า", "BOT:ITEM_OK"),
                    ("❌ ยกเลิก", "BOT:CANCEL"),
                ],
            ),
        )
        return

    # CANCEL (allowed here)
    if cmd == "BOT" and parts[:1] == ["CANCEL"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ITEM_OK -> ask name
    if cmd == "BOT" and parts[:1] == ["ITEM_OK"]:
        if not require_state(uid, reply_token, "WAIT_CONFIRM_ITEM"):
            return

        # reload latest
        session = get_session(uid) or {}
        data = session.get("data", {}) or {}

        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์ ชื่อ-นามสกุล ผู้รับ:"}])
        set_session(uid, "WAIT_NAME", data)
        return

    # WAIT_NAME
    if state == "WAIT_NAME":
        name = plain
        if not is_valid_name(name):
            reply_message(reply_token, [{"type": "text", "text": "ชื่อ-นามสกุลสั้นเกินไป ลองใหม่อีกครั้งครับ"}])
            return
        data["name"] = name
        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์เบอร์โทร (10 หลัก ขึ้นต้น 0):"}])
        set_session(uid, "WAIT_PHONE", data)
        return

    # WAIT_PHONE
    if state == "WAIT_PHONE":
        phone = plain
        if not is_valid_phone_10(phone):
            reply_message(reply_token, [{"type": "text", "text": "เบอร์ไม่ถูกต้อง ❌\nต้องเป็น 10 หลัก และขึ้นต้นด้วย 0\nพิมพ์ใหม่อีกครั้ง:"}])
            return
        data["phone"] = phone.strip().replace(" ", "").replace("-", "")
        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์ที่อยู่จัดส่ง (อย่างน้อย 10 ตัวอักษร):"}])
        set_session(uid, "WAIT_ADDRESS", data)
        return

    # WAIT_ADDRESS -> final summary + final confirm (ONLY ONE BUTTON)
    if state == "WAIT_ADDRESS":
        address = plain
        if not is_valid_address(address):
            reply_message(reply_token, [{"type": "text", "text": "ที่อยู่สั้นเกินไป ลองใหม่อีกครั้งครับ"}])
            return
        data["address"] = address

        # Prepare idempotency token for final confirm
        data["confirm_token"] = gen_token()
        data["confirm_lock"] = False
        data["payment_status"] = "PENDING"

        summary = (
            "📦 สรุปทั้งหมด\n"
            f"สินค้า: {data.get('color')} / {data.get('size')}\n"
            f"จำนวน: {data.get('qty')} ตัว\n"
            f"รวม: {data.get('total')} บาท\n\n"
            f"ผู้รับ: {data.get('name')}\n"
            f"เบอร์: {data.get('phone')}\n"
            f"ที่อยู่: {data.get('address')}\n\n"
            "กดปุ่มด้านล่างเพื่อยืนยันและรอชำระเงิน"
        )

        reply_message(
            reply_token,
            build_quick_or_fallback(
                summary,
                [
                    ("✅ ยืนยันและรอชำระเงิน", "BOT:FINAL_CONFIRM"),
                ],
            ),
        )
        set_session(uid, "WAIT_FINAL_CONFIRM", data)
        return

    # FINAL_CONFIRM (Idempotent + Lock)  (NO CANCEL here)
    if cmd == "BOT" and parts[:1] == ["FINAL_CONFIRM"]:
        if not require_state(uid, reply_token, "WAIT_FINAL_CONFIRM"):
            return

        session = get_session(uid) or {}
        data = session.get("data", {}) or {}

        needed = ["color", "size", "qty", "price", "total", "name", "phone", "address", "confirm_token"]
        if any(k not in data for k in needed):
            send_menu(reply_token)
            return

        if data.get("confirm_lock") is True:
            reply_message(reply_token, [{"type": "text", "text": "ระบบกำลังดำเนินการ ✅"}])
            return

        # lock immediately
        data["confirm_lock"] = True
        set_session(uid, "WAIT_FINAL_CONFIRM", data)

        from services.order_service import find_order_by_confirm_token, create_order
        existed = find_order_by_confirm_token(data["confirm_token"])
        if existed:
            clear_session(uid)
            reply_message(reply_token, [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {existed}\nสถานะชำระเงิน: PENDING"}])
            return

        # deduct stock
        ok, remain = deduct_stock(data["color"], data["size"], int(data["qty"]))
        if not ok:
            clear_session(uid)
            reply_message(
                reply_token,
                build_quick_or_fallback(
                    "สต๊อกไม่พอ ❌ (อาจมีคนสั่งตัดหน้าคุณ)\nกดสั่งซื้อใหม่ได้เลย",
                    [("🛒 สั่งซื้อ", "BOT:ORDER"), ("เมนู", "เมนู")],
                ),
            )
            return

        order_id = create_order(uid, data)

        from services.admin_service import notify_admin_new_order
        notify_admin_new_order(order_id, data, remain)

        clear_session(uid)
        reply_message(
            reply_token,
            [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}\nสถานะชำระเงิน: PENDING"}],
        )
        return

    # ADMIN CHAT
    if cmd == "BOT" and parts[:1] == ["ADMIN"]:
        set_session(uid, "ADMIN_CHAT", {})
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ข้อความส่งหาแอดมินได้เลย"}])
        return

    if state == "ADMIN_CHAT":
        from services.admin_service import forward_to_admin
        forward_to_admin(uid, plain)
        reply_message(reply_token, [{"type": "text", "text": "ส่งถึงแอดมินแล้ว ✅"}])
        return

    # DEFAULT
    send_menu(reply_token)

# ----------------------------------------------------------
# Entry
# ----------------------------------------------------------

def handle_event(event: dict):
    try:
        if event.get("type") != "message":
            return
        message = event.get("message", {})
        if message.get("type") != "text":
            return

        uid = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = (message.get("text") or "").strip()

        handle(uid, reply_token, text)

    except Exception as e:
        print("ORDER FLOW ERROR:", e)
