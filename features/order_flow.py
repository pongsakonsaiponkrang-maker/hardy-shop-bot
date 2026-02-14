# ==========================================================
# HARDY ORDER FLOW - CLEAN V1
# Quick Reply Only / Small Buttons / Production Ready
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
from services.order_service import create_order
from services.admin_service import notify_admin_new_order


# ==========================================================
# QUICK REPLY BUILDER (Small Buttons)
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
                        "label": label[:20],  # กัน label ยาวเกิน
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
# MAIN FLOW LOGIC
# ==========================================================

def handle(uid: str, reply_token: str, text: str):

    # ---------------- MENU ----------------
    if text in ["เมนู", "menu", "hi", "Hi"]:
        send_menu(reply_token)
        return

    # ---------------- ORDER START ----------------
    if text == "BOT:ORDER":
        colors = get_available_colors()

        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]
        reply_message(reply_token, [quick("เลือกสี:", buttons)])
        return

    # ---------------- COLOR ----------------
    if text.startswith("BOT:COLOR:"):
        color = text.split(":", 2)[2]

        sizes = get_available_sizes(color)

        if not sizes:
            reply_message(reply_token, [{"type": "text", "text": "สีนี้หมด ❌"}])
            return

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            label = f"{s} | {price}฿ | {stock}"
            buttons.append((label, f"BOT:SIZE:{color}:{s}"))

        reply_message(
            reply_token,
            [quick(f"สี {color}\nเลือกไซส์:", buttons)],
        )
        return

    # ---------------- SIZE ----------------
    if text.startswith("BOT:SIZE:"):
        _, _, color, size = text.split(":")

        stock = get_stock(color, size)
        price = get_price(color, size)

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
        return

    # ---------------- QTY ----------------
    if text.startswith("BOT:QTY:"):
        _, _, color, size, qty = text.split(":")
        qty = int(qty)
        price = get_price(color, size)

        set_session(
            uid,
            "WAIT_CONFIRM",
            {
                "color": color,
                "size": size,
                "qty": qty,
                "price": price,
            },
        )

        total = qty * price

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
        session = get_session(uid)
        data = session.get("data", {})

        if not data:
            send_menu(reply_token)
            return

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
            [
                {"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}"},
            ],
        )
        return

    # ---------------- CANCEL ----------------
    if text == "BOT:CANCEL":
        clear_session(uid)
        send_menu(reply_token)
        return

    # ---------------- ADMIN MODE ----------------
    if text == "BOT:ADMIN":
        reply_message(
            reply_token,
            [{"type": "text", "text": "พิมพ์ข้อความส่งหาแอดมินได้เลย"}],
        )
        return

    # ---------------- DEFAULT ----------------
    send_menu(reply_token)


# ==========================================================
# ENTRY POINT FOR APP
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
