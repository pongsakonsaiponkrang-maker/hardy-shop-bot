# ==========================================================
# HARDY ORDER FLOW - V3 PRODUCTION SAFE
# Strict State / Anti-Skip / Anti-Double Confirm
# ==========================================================

from typing import List, Tuple
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

# ==========================================================
# QUICK REPLY
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
                    ("🎨 ดูสี", "BOT:COLORS"),
                    ("💬 คุยกับแอดมิน", "BOT:ADMIN"),
                ],
            )
        ],
    )


# ==========================================================
# SAFE VALIDATION
# ==========================================================

def require_state(uid, reply_token, expected_state):
    session = get_session(uid)
    if session.get("state") != expected_state:
        send_menu(reply_token)
        return False
    return True


# ==========================================================
# MAIN FLOW
# ==========================================================

def handle(uid: str, reply_token: str, text: str):

    session = get_session(uid)
    state = session.get("state", "IDLE")
    data = session.get("data", {})

    # ---------------- MENU RESET ----------------
    if text.lower() in ["เมนู", "menu", "hi", "hello"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ---------------- START ORDER ----------------
    if text == "BOT:ORDER":
        clear_session(uid)

        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]
        reply_message(reply_token, [quick("เลือกสี:", buttons)])

        set_session(uid, "WAIT_COLOR", {})
        return

    # ---------------- COLOR ----------------
    if text.startswith("BOT:COLOR:"):

        if not require_state(uid, reply_token, "WAIT_COLOR"):
            return

        parts = text.split(":", 2)
        if len(parts) != 3:
            send_menu(reply_token)
            return

        color = parts[2]
        sizes = get_available_sizes(color)

        if not sizes:
            reply_message(reply_token, [{"type": "text", "text": "สีนี้หมด ❌"}])
            return

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            buttons.append(
                (f"{s} | {price}฿ | {stock}", f"BOT:SIZE:{color}:{s}")
            )

        reply_message(reply_token, [quick(f"สี {color}\nเลือกไซส์:", buttons)])
        set_session(uid, "WAIT_SIZE", {"color": color})
        return

    # ---------------- SIZE ----------------
    if text.startswith("BOT:SIZE:"):

        if not require_state(uid, reply_token, "WAIT_SIZE"):
            return

        parts = text.split(":")
        if len(parts) != 4:
            send_menu(reply_token)
            return

        _, _, color, size = parts

        if data.get("color") != color:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        price = get_price(color, size)

        if stock <= 0:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกหมด ❌"}])
            return

        buttons = []
        for n in range(1, min(stock, 5) + 1):
            buttons.append((str(n), f"BOT:QTY:{color}:{size}:{n}"))

        reply_message(
            reply_token,
            [
                quick(
                    f"{color} / {size}\nราคา {price} บาท\nเลือกจำนวน:",
                    buttons,
                )
            ],
        )

        set_session(uid, "WAIT_QTY", {"color": color, "size": size})
        return

    # ---------------- QTY ----------------
    if text.startswith("BOT:QTY:"):

        if not require_state(uid, reply_token, "WAIT_QTY"):
            return

        parts = text.split(":")
        if len(parts) != 5:
            send_menu(reply_token)
            return

        _, _, color, size, qty_str = parts

        if data.get("color") != color or data.get("size") != size:
            send_menu(reply_token)
            return

        qty = int(qty_str)
        stock = get_stock(color, size)

        if qty > stock:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        price = get_price(color, size)
        total = qty * price

        set_session(
            uid,
            "WAIT_CONFIRM",
            {
                "color": color,
                "size": size,
                "qty": qty,
                "price": price,
                "total": total,
                "confirmed": False,
            },
        )

        reply_message(
            reply_token,
            [
                quick(
                    f"🧾 สรุป\n{color} / {size}\n"
                    f"{qty} ตัว\n"
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

        if not require_state(uid, reply_token, "WAIT_CONFIRM"):
            return

        if data.get("confirmed"):
            send_menu(reply_token)
            return

        ok, remain = deduct_stock(
            data["color"],
            data["size"],
            data["qty"],
        )

        if not ok:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            clear_session(uid)
            return

        from services.order_service import create_order
        from services.admin_service import notify_admin_new_order

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

    # ---------------- ADMIN CHAT ----------------
    if text == "BOT:ADMIN":
        set_session(uid, "ADMIN_CHAT", {})
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ข้อความส่งหาแอดมินได้เลย"}])
        return

    if state == "ADMIN_CHAT":
        from services.admin_service import forward_to_admin
        forward_to_admin(uid, text)
        reply_message(reply_token, [{"type": "text", "text": "ส่งถึงแอดมินแล้ว ✅"}])
        return

    # ---------------- DEFAULT ----------------
    send_menu(reply_token)


# ==========================================================
# ENTRY
# ==========================================================

def handle_event(event: dict):
    try:
        if event.get("type") != "message":
            return

        message = event.get("message", {})
        if message.get("type") != "text":
            return

        uid = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = message.get("text", "").strip()

        handle(uid, reply_token, text)

    except Exception as e:
        print("ORDER FLOW ERROR:", e)
