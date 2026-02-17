# ==========================================================
# HARDY ORDER FLOW - PRODUCTION FINAL
# Clean State Machine
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
from core.utils import safe_int, gen_token


# ==========================================================
# Helpers
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


def parse_payload(text):
    if not text.startswith("BOT:"):
        return None, []
    parts = text.split(":")
    return parts[0], parts[1:]


def valid_phone(p):
    p = p.replace("-", "").replace(" ", "")
    return len(p) == 10 and p.isdigit() and p.startswith("0")


def valid_name(n):
    return len(n.strip()) >= 3


def valid_address(a):
    return len(a.strip()) >= 10


# ==========================================================
# Main Flow
# ==========================================================

def handle(uid, reply_token, text):

    text = text.strip()
    session = get_session(uid) or {}
    state = session.get("state", "IDLE")
    data = session.get("data", {}) or {}

    # ------------------------------------------------------
    # RESET
    # ------------------------------------------------------

    if text.lower() in ["เมนู", "menu", "hi", "start"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ------------------------------------------------------
    # STATE FIRST (สำคัญมาก)
    # ------------------------------------------------------

    if state == "WAIT_NAME":
        if not valid_name(text):
            reply_message(reply_token, [{"type": "text", "text": "ชื่อสั้นเกินไป"}])
            return

        data["name"] = text
        set_session(uid, "WAIT_PHONE", data)
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์เบอร์โทร (10 หลัก):"}])
        return

    if state == "WAIT_PHONE":
        if not valid_phone(text):
            reply_message(reply_token, [{"type": "text", "text": "เบอร์ไม่ถูกต้อง"}])
            return

        data["phone"] = text
        set_session(uid, "WAIT_ADDRESS", data)
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ที่อยู่จัดส่ง:"}])
        return

    if state == "WAIT_ADDRESS":
        if not valid_address(text):
            reply_message(reply_token, [{"type": "text", "text": "ที่อยู่สั้นเกินไป"}])
            return

        data["address"] = text
        data["confirm_token"] = gen_token()
        data["payment_status"] = "PENDING"

        set_session(uid, "WAIT_FINAL_CONFIRM", data)

        reply_message(
            reply_token,
            [
                quick(
                    f"📦 ยืนยันทั้งหมด\n"
                    f"{data['color']} / {data['size']}\n"
                    f"{data['qty']} ตัว\nรวม {data['total']} บาท\n\n"
                    f"{data['name']}\n{data['phone']}\n{data['address']}",
                    [("✅ ยืนยันและรอชำระเงิน", "BOT:FINAL_CONFIRM")],
                )
            ],
        )
        return

    # ------------------------------------------------------
    # COMMAND HANDLING
    # ------------------------------------------------------

    cmd, parts = parse_payload(text)

    if cmd == "BOT" and parts == ["ORDER"]:
        clear_session(uid)

        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        set_session(uid, "WAIT_COLOR", {})

        reply_message(
            reply_token,
            [quick("เลือกสี:", [(c, f"BOT:COLOR:{c}") for c in colors])],
        )
        return

    if cmd == "BOT" and parts[:1] == ["COLOR"]:
        if state != "WAIT_COLOR":
            send_menu(reply_token)
            return

        color = parts[1]
        sizes = get_available_sizes(color)

        if not sizes:
            reply_message(reply_token, [{"type": "text", "text": "สีนี้หมด ❌"}])
            return

        set_session(uid, "WAIT_SIZE", {"color": color})

        reply_message(
            reply_token,
            [
                quick(
                    f"สี {color}\nเลือกไซส์:",
                    [
                        (f"{s} | {get_price(color, s)}฿ | {get_stock(color, s)}",
                         f"BOT:SIZE:{color}:{s}")
                        for s in sizes
                    ],
                )
            ],
        )
        return

    if cmd == "BOT" and parts[:1] == ["SIZE"]:
        if state != "WAIT_SIZE":
            send_menu(reply_token)
            return

        color, size = parts[1], parts[2]

        stock = get_stock(color, size)
        if stock <= 0:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกหมด ❌"}])
            return

        set_session(uid, "WAIT_QTY", {"color": color, "size": size})

        reply_message(
            reply_token,
            [
                quick(
                    f"{color} / {size}\nเลือกจำนวน:",
                    [
                        (str(i), f"BOT:QTY:{color}:{size}:{i}")
                        for i in range(1, min(stock, 5) + 1)
                    ],
                )
            ],
        )
        return

    if cmd == "BOT" and parts[:1] == ["QTY"]:
        if state != "WAIT_QTY":
            send_menu(reply_token)
            return

        color, size, qty_str = parts[1], parts[2], parts[3]
        qty = safe_int(qty_str, 0)

        stock = get_stock(color, size)
        if qty <= 0 or qty > stock:
            reply_message(reply_token, [{"type": "text", "text": "จำนวนไม่ถูกต้อง"}])
            return

        price = get_price(color, size)
        total = price * qty

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
            [
                quick(
                    f"🧾 สรุปสินค้า\n{color} / {size}\n{qty} ตัว\nรวม {total} บาท",
                    [("✅ ยืนยันสินค้า", "BOT:ITEM_OK")],
                )
            ],
        )
        return

    if cmd == "BOT" and parts == ["ITEM_OK"]:
        if state != "WAIT_CONFIRM_ITEM":
            send_menu(reply_token)
            return

        set_session(uid, "WAIT_NAME", data)
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ชื่อ-นามสกุลผู้รับ:"}])
        return

    if cmd == "BOT" and parts == ["FINAL_CONFIRM"]:
        if state != "WAIT_FINAL_CONFIRM":
            send_menu(reply_token)
            return

        ok, _ = deduct_stock(data["color"], data["size"], data["qty"])
        if not ok:
            clear_session(uid)
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        order_id = create_order(uid, data)
        clear_session(uid)

        reply_message(
            reply_token,
            [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}"}],
        )
        return

    send_menu(reply_token)


def send_menu(reply_token):
    reply_message(
        reply_token,
        [
            quick(
                "👖 HARDY\nเลือกเมนู:",
                [
                    ("🛒 สั่งซื้อ", "BOT:ORDER"),
                    ("🎨 ดูสี", "BOT:COLORS"),
                ],
            )
        ],
    )


def handle_event(event):
    if event.get("type") != "message":
        return

    msg = event.get("message", {})
    if msg.get("type") != "text":
        return

    uid = event["source"]["userId"]
    reply_token = event["replyToken"]
    text = msg.get("text", "")

    handle(uid, reply_token, text)
