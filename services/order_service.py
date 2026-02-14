# ==========================================================
# HARDY ORDER FLOW V4 - PRODUCTION FULL FORM (REWRITE)
# - Strict step-by-step state machine
# - Phone/Name validation
# - Anti-spam (2s) stored in session data (compatible with set_session)
# - Anti-skip payload
# - Anti-double confirm
# - Admin push full detail
# ==========================================================

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
from services.order_service import create_order
from services.admin_service import notify_admin_new_order
from core.utils import safe_int

import re
import time
from typing import List, Tuple, Dict, Any


# ==========================================================
# QUICK REPLY BUILDER
# ==========================================================

def quick(text: str, buttons: List[Tuple[str, str]]):
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": label[:20],
                        "text": payload,
                    },
                }
                for label, payload in buttons
            ]
        },
    }


def text_msg(t: str):
    return {"type": "text", "text": t}


# ==========================================================
# VALIDATION
# ==========================================================

def normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")

def valid_phone(phone: str) -> bool:
    digits = normalize_phone(phone)
    # ไทยทั่วไป 10 หลัก (0xxxxxxxxx)
    return len(digits) == 10 and digits.startswith("0")

def valid_name(name: str) -> bool:
    name = (name or "").strip()
    # กันสแปม/มั่ว: ต้องมีอย่างน้อย 2 ตัวอักษร และไม่ใช่ตัวเลขล้วน
    if len(name) < 2:
        return False
    if re.fullmatch(r"\d+", name):
        return False
    return True

def valid_address(addr: str) -> bool:
    addr = (addr or "").strip()
    return len(addr) >= 10


# ==========================================================
# MENU
# ==========================================================

def send_menu(reply_token: str):
    reply_message(
        reply_token,
        [
            quick(
                "👖 HARDY\nเลือกเมนู:",
                [
                    ("🛒 สั่งซื้อ", "BOT:ORDER"),
                    ("💬 คุยกับแอดมิน", "BOT:ADMIN"),
                ],
            )
        ],
    )


# ==========================================================
# SESSION HELPERS
# ==========================================================

def get_state(uid: str) -> Tuple[str, Dict[str, Any]]:
    session = get_session(uid) or {}
    return session.get("state", "IDLE"), (session.get("data", {}) or {})

def save_state(uid: str, state: str, data: Dict[str, Any]):
    set_session(uid, state, data or {})

def reset_to_menu(uid: str, reply_token: str):
    clear_session(uid)
    send_menu(reply_token)

def is_menu_text(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in ["เมนู", "menu", "hi", "hello", "start"]

def is_cancel_text(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in ["ยกเลิก", "cancel", "bot:cancel"]


# ==========================================================
# ANTI SPAM (2 seconds lock) - stored in data
# ==========================================================

def spam_guard(uid: str, state: str, data: Dict[str, Any], cooldown_sec: int = 2) -> bool:
    now = time.time()
    last = float(data.get("_last_action_time", 0) or 0)

    if now - last < cooldown_sec:
        # ไม่ตอบกลับ ลด spam
        return False

    data["_last_action_time"] = now
    save_state(uid, state, data)
    return True


# ==========================================================
# PAYLOAD PARSERS (safe)
# ==========================================================

def parse_color(text: str) -> str:
    # BOT:COLOR:<color>
    parts = (text or "").split(":", 2)
    if len(parts) != 3:
        return ""
    return parts[2].strip()

def parse_size(text: str) -> Tuple[str, str]:
    # BOT:SIZE:<color>:<size>
    parts = (text or "").split(":")
    if len(parts) != 4:
        return "", ""
    return parts[2].strip(), parts[3].strip()

def parse_qty(text: str) -> Tuple[str, str, int]:
    # BOT:QTY:<color>:<size>:<qty>
    parts = (text or "").split(":")
    if len(parts) != 5:
        return "", "", 0
    color = parts[2].strip()
    size = parts[3].strip()
    qty = safe_int(parts[4], 0)
    return color, size, qty


# ==========================================================
# MAIN FLOW
# ==========================================================

def handle(uid: str, reply_token: str, text: str):
    state, data = get_state(uid)
    text = (text or "").strip()

    # --- menu / cancel usable anytime ---
    if is_menu_text(text):
        reset_to_menu(uid, reply_token)
        return

    if is_cancel_text(text) or text == "BOT:CANCEL":
        reset_to_menu(uid, reply_token)
        return

    # --- anti spam ---
    if not spam_guard(uid, state, data):
        return

    # ---------------- ADMIN MODE ENTRY ----------------
    if text == "BOT:ADMIN":
        save_state(uid, "ADMIN_CHAT", {"_last_action_time": data.get("_last_action_time", time.time())})
        reply_message(reply_token, [text_msg("พิมพ์ข้อความส่งหาแอดมินได้เลยครับ")])
        return

    if state == "ADMIN_CHAT":
        from services.admin_service import forward_to_admin
        forward_to_admin(uid, text)
        reply_message(reply_token, [text_msg("ส่งข้อความถึงแอดมินแล้ว ✅")])
        return

    # ---------------- START ORDER ----------------
    if text == "BOT:ORDER":
        colors = get_available_colors() or []
        if not colors:
            reply_message(reply_token, [text_msg("สินค้าหมด ❌")])
            return

        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]
        reply_message(reply_token, [quick("เลือกสี:", buttons)])

        save_state(uid, "WAIT_COLOR", {"_last_action_time": data.get("_last_action_time", time.time())})
        return

    # ---------------- SELECT COLOR ----------------
    if text.startswith("BOT:COLOR:"):
        if state != "WAIT_COLOR":
            reset_to_menu(uid, reply_token)
            return

        color = parse_color(text)
        if not color:
            reset_to_menu(uid, reply_token)
            return

        sizes = get_available_sizes(color) or []
        if not sizes:
            reply_message(reply_token, [text_msg("สีนี้หมด ❌")])
            return

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            label = f"{s} | {price}฿ | {stock}"
            buttons.append((label, f"BOT:SIZE:{color}:{s}"))

        reply_message(reply_token, [quick(f"สี {color}\nเลือกไซส์:", buttons)])

        save_state(uid, "WAIT_SIZE", {"color": color, "_last_action_time": data.get("_last_action_time", time.time())})
        return

    # ---------------- SELECT SIZE ----------------
    if text.startswith("BOT:SIZE:"):
        if state != "WAIT_SIZE":
            reset_to_menu(uid, reply_token)
            return

        color, size = parse_size(text)
        if not color or not size:
            reset_to_menu(uid, reply_token)
            return

        # anti skip: color ต้องตรงกับที่เลือกไว้
        if data.get("color") != color:
            reset_to_menu(uid, reply_token)
            return

        stock = get_stock(color, size)
        price = get_price(color, size)

        if stock <= 0:
            reply_message(reply_token, [text_msg("สต๊อกหมด ❌")])
            return

        buttons = [(str(n), f"BOT:QTY:{color}:{size}:{n}") for n in range(1, min(stock, 5) + 1)]
        reply_message(reply_token, [quick(f"{color} / {size}\nราคา {price} บาท\nเลือกจำนวน:", buttons)])

        save_state(
            uid,
            "WAIT_QTY",
            {
                "color": color,
                "size": size,
                "_last_action_time": data.get("_last_action_time", time.time()),
            },
        )
        return

    # ---------------- SELECT QTY ----------------
    if text.startswith("BOT:QTY:"):
        if state != "WAIT_QTY":
            reset_to_menu(uid, reply_token)
            return

        color, size, qty = parse_qty(text)
        if not color or not size or qty <= 0:
            reset_to_menu(uid, reply_token)
            return

        # anti skip: ต้องตรงกับที่เลือกไว้
        if data.get("color") != color or data.get("size") != size:
            reset_to_menu(uid, reply_token)
            return

        stock = get_stock(color, size)
        if qty > stock:
            reply_message(reply_token, [text_msg("สต๊อกไม่พอ ❌")])
            return

        price = get_price(color, size)

        save_state(
            uid,
            "WAIT_NAME",
            {
                "color": color,
                "size": size,
                "qty": qty,
                "price": price,
                "_last_action_time": data.get("_last_action_time", time.time()),
            },
        )

        reply_message(reply_token, [text_msg("กรุณาพิมพ์ชื่อ-นามสกุลผู้รับ:")])
        return

    # ---------------- NAME ----------------
    if state == "WAIT_NAME":
        if not valid_name(text):
            reply_message(reply_token, [text_msg("ชื่อไม่ถูกต้อง ❌\nพิมพ์ชื่อ-นามสกุลใหม่อีกครั้ง")])
            return

        data["name"] = text.strip()
        save_state(uid, "WAIT_PHONE", data)

        reply_message(reply_token, [text_msg("กรุณาพิมพ์เบอร์โทร (10 หลัก):")])
        return

    # ---------------- PHONE ----------------
    if state == "WAIT_PHONE":
        if not valid_phone(text):
            reply_message(reply_token, [text_msg("เบอร์ไม่ถูกต้อง ❌\nตัวอย่าง: 0891234567")])
            return

        data["phone"] = normalize_phone(text)
        save_state(uid, "WAIT_ADDRESS", data)

        reply_message(reply_token, [text_msg("กรุณาพิมพ์ที่อยู่จัดส่ง:")])
        return

    # ---------------- ADDRESS ----------------
    if state == "WAIT_ADDRESS":
        if not valid_address(text):
            reply_message(reply_token, [text_msg("ที่อยู่สั้นเกินไป ❌\nกรุณาพิมพ์รายละเอียดเพิ่ม (อย่างน้อย 10 ตัวอักษร)")])
            return

        data["address"] = text.strip()

        total = int(data["qty"]) * int(data["price"])
        data["total"] = total
        data["_confirmed"] = False  # anti double confirm flag

        save_state(uid, "WAIT_CONFIRM", data)

        reply_message(
            reply_token,
            [
                quick(
                    "🧾 สรุปออเดอร์\n"
                    f"{data['color']} / {data['size']}\n"
                    f"{data['qty']} ตัว\n"
                    f"ผู้รับ: {data['name']}\n"
                    f"โทร: {data['phone']}\n"
                    f"ที่อยู่: {data['address']}\n"
                    f"รวม {total} บาท",
                    [
                        ("✅ ยืนยัน", "BOT:CONFIRM"),
                        ("❌ ยกเลิก", "BOT:CANCEL"),
                    ],
                )
            ],
        )
        return

    # ---------------- CONFIRM ----------------
    if text == "BOT:CONFIRM":
        if state != "WAIT_CONFIRM":
            reset_to_menu(uid, reply_token)
            return

        # anti double confirm
        if data.get("_confirmed") is True:
            reset_to_menu(uid, reply_token)
            return

        # mark confirmed first (ลดโอกาส confirm ซ้ำจาก resend)
        data["_confirmed"] = True
        save_state(uid, "WAIT_CONFIRM", data)

        ok, remain = deduct_stock(data["color"], data["size"], data["qty"])
        if not ok:
            reply_message(reply_token, [text_msg("สต๊อกไม่พอ ❌")])
            clear_session(uid)
            return

        order_id = create_order(uid, data)
        notify_admin_new_order(order_id, data, remain)

        clear_session(uid)

        reply_message(reply_token, [text_msg(f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}\nแอดมินจะติดต่อกลับครับ")])
        return

    # ---------------- DEFAULT ----------------
    send_menu(reply_token)


# ==========================================================
# ENTRY POINT
# ==========================================================

def handle_event(event: dict):
    try:
        if event.get("type") != "message":
            return

        msg = event.get("message", {})
        if msg.get("type") != "text":
            return

        uid = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = (msg.get("text") or "").strip()

        handle(uid, reply_token, text)

    except Exception as e:
        print("ORDER FLOW ERROR:", e)
