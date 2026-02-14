# ==========================================================
# HARDY ORDER FLOW V4 - FULL FORM SYSTEM
# - Step by step form
# - Phone validation
# - Name validation
# - Anti spam
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


# ==========================================================
# QUICK REPLY BUILDER
# ==========================================================

def quick(text, buttons):
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


# ==========================================================
# ANTI SPAM (2 seconds lock)
# ==========================================================

def spam_guard(uid):
    session = get_session(uid)
    last = session.get("last_action_time", 0)

    if time.time() - last < 2:
        return False

    session["last_action_time"] = time.time()
    set_session(uid, session.get("state", ""), session.get("data", {}))
    return True


# ==========================================================
# VALIDATION
# ==========================================================

def valid_phone(phone):
    digits = re.sub(r"\D", "", phone)
    return len(digits) == 10


def valid_name(name):
    return len(name.strip()) >= 2


# ==========================================================
# MENU
# ==========================================================

def send_menu(reply_token):
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
# MAIN FLOW
# ==========================================================

def handle(uid, reply_token, text):

    if not spam_guard(uid):
        return

    session = get_session(uid)
    state = session.get("state")
    data = session.get("data", {})

    # ---------------- START ----------------
    if text in ["hi", "Hi", "เมนู", "menu"]:
        send_menu(reply_token)
        return

    # ---------------- ORDER ----------------
    if text == "BOT:ORDER":
        colors = get_available_colors()
        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]

        reply_message(reply_token, [quick("เลือกสี:", buttons)])
        return

    # ---------------- COLOR ----------------
    if text.startswith("BOT:COLOR:"):
        color = text.split(":", 2)[2]
        sizes = get_available_sizes(color)

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            label = f"{s} | {price}฿ | {stock}"
            buttons.append((label, f"BOT:SIZE:{color}:{s}"))

        reply_message(reply_token, [quick(f"{color}\nเลือกไซส์:", buttons)])
        return

    # ---------------- SIZE ----------------
    if text.startswith("BOT:SIZE:"):
        _, _, color, size = text.split(":")
        stock = get_stock(color, size)
        price = get_price(color, size)

        buttons = [
            (str(n), f"BOT:QTY:{color}:{size}:{n}")
            for n in range(1, min(stock, 5) + 1)
        ]

        reply_message(
            reply_token,
            [
                quick(
                    f"{color} / {size}\nราคา {price} บาท\nเลือกจำนวน:",
                    buttons,
                )
            ],
        )
        return

    # ---------------- QTY ----------------
    if text.startswith("BOT:QTY:"):
        _, _, color, size, qty = text.split(":")
        qty = int(qty)

        set_session(uid, "WAIT_NAME", {
            "color": color,
            "size": size,
            "qty": qty,
            "price": get_price(color, size),
        })

        reply_message(
            reply_token,
            [{"type": "text", "text": "กรุณาพิมพ์ชื่อ-นามสกุลผู้รับ:"}],
        )
        return

    # ---------------- NAME ----------------
    if state == "WAIT_NAME":
        if not valid_name(text):
            reply_message(reply_token, [{"type": "text", "text": "ชื่อไม่ถูกต้อง ❌"}])
            return

        data["name"] = text.strip()
        set_session(uid, "WAIT_PHONE", data)

        reply_message(
            reply_token,
            [{"type": "text", "text": "กรุณาพิมพ์เบอร์โทร (10 หลัก):"}],
        )
        return

    # ---------------- PHONE ----------------
    if state == "WAIT_PHONE":
        if not valid_phone(text):
            reply_message(reply_token, [{"type": "text", "text": "เบอร์ไม่ถูกต้อง ❌"}])
            return

        data["phone"] = re.sub(r"\D", "", text)
        set_session(uid, "WAIT_ADDRESS", data)

        reply_message(
            reply_token,
            [{"type": "text", "text": "กรุณาพิมพ์ที่อยู่จัดส่ง:"}],
        )
        return

    # ---------------- ADDRESS ----------------
    if state == "WAIT_ADDRESS":
        if len(text.strip()) < 10:
            reply_message(reply_token, [{"type": "text", "text": "ที่อยู่สั้นเกินไป ❌"}])
            return

        data["address"] = text.strip()
        set_session(uid, "WAIT_CONFIRM", data)

        total = data["qty"] * data["price"]

        reply_message(
            reply_token,
            [
                quick(
                    f"🧾 สรุป\n"
                    f"{data['color']} / {data['size']}\n"
                    f"{data['qty']} ตัว\n"
                    f"{data['name']}\n"
                    f"{data['phone']}\n"
                    f"{data['address']}\n"
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
        ok, remain = deduct_stock(
            data["color"],
            data["size"],
            data["qty"],
        )

        if not ok:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        order_id = create_order(uid, data)

        notify_admin_new_order(order_id, data, remain)

        clear_session(uid)

        reply_message(
            reply_token,
            [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}"}],
        )
        return

    # ---------------- CANCEL ----------------
    if text == "BOT:CANCEL":
        clear_session(uid)
        send_menu(reply_token)
        return

    send_menu(reply_token)


# ==========================================================
# ENTRY POINT
# ==========================================================

def handle_event(event):
    if event.get("type") != "message":
        return

    msg = event.get("message", {})
    if msg.get("type") != "text":
        return

    uid = event["source"]["userId"]
    reply_token = event["replyToken"]
    text = msg.get("text", "").strip()

    handle(uid, reply_token, text)
