# ==========================================================
# HARDY ORDER FLOW - CLEAN FINAL VERSION
# ==========================================================

from integrations.line_api import reply_message
from services.stock_service import (
    get_available_colors,
    get_available_sizes,
    get_stock,
    get_price,
    deduct_stock,
)
from services.session_service import get_session, set_session, clear_session
from services.order_service import create_order
from services.admin_service import (
    notify_admin_context,
    forward_to_admin,
    is_admin_uid,
    admin_close_order,
)
from core.utils import safe_int, gen_token


# ----------------------------------------------------------
# UI
# ----------------------------------------------------------

def quick(text, buttons, include_admin=True, include_menu=True):
    items = buttons.copy()

    if include_admin:
        items.append(("👩‍💼 คุยกับเจ้าหน้าที่", "BOT:ADMIN"))
    if include_menu:
        items.append(("🏠 กลับสู่เมนู", "BOT:MENU"))

    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "postback",
                        "label": label[:20],
                        "data": payload,
                        "displayText": label,
                    },
                }
                for label, payload in items
            ]
        },
    }


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
                include_admin=True,
                include_menu=False,
            )
        ],
    )


def parse_payload(text):
    if not text.startswith("BOT:"):
        return None, []
    parts = text.split(":")
    return parts[0], parts[1:]


# ----------------------------------------------------------
# MAIN
# ----------------------------------------------------------

def handle(uid, reply_token, text):

    text = text.strip()
    session = get_session(uid) or {}
    state = session.get("state", "IDLE")
    data = session.get("data", {}) or {}

    # ------------------------------------------------------
    # ADMIN CLOSE COMMAND
    # ------------------------------------------------------
    if is_admin_uid(uid) and text.upper().startswith("CLOSE:"):
        order_id = text.split(":", 1)[1].strip()
        ok = admin_close_order(order_id)
        reply_message(
            reply_token,
            [{"type": "text", "text": f"{'✅' if ok else '❌'} ปิดออเดอร์ {order_id}"}],
        )
        return

    # ------------------------------------------------------
    # NORMAL MENU TEXT
    # ------------------------------------------------------
    if text.lower() in ["menu", "เมนู", "hi", "start"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ------------------------------------------------------
    # COMMAND HANDLING FIRST
    # ------------------------------------------------------
    cmd, parts = parse_payload(text)

    # MENU BUTTON
    if cmd == "BOT" and parts == ["MENU"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ADMIN ENTRY
    if cmd == "BOT" and parts == ["ADMIN"]:
        context = data.copy()
        clear_session(uid)

        notify_admin_context(uid, context)
        set_session(uid, "ADMIN_CHAT", {})

        reply_message(
            reply_token,
            [
                quick(
                    "👩‍💼 เชื่อมต่อเจ้าหน้าที่แล้ว\nพิมพ์ข้อความได้เลย",
                    [],
                    include_admin=False,
                    include_menu=True,
                )
            ],
        )
        return

    # ------------------------------------------------------
    # ADMIN CHAT MODE (อย่ารับ BOT:)
    # ------------------------------------------------------
    if state == "ADMIN_CHAT" and not text.startswith("BOT:"):
        forward_to_admin(uid, text)
        reply_message(
            reply_token,
            [
                quick(
                    "ส่งถึงเจ้าหน้าที่แล้ว ✅",
                    [],
                    include_admin=False,
                    include_menu=True,
                )
            ],
        )
        return

    # ------------------------------------------------------
    # ORDER FLOW
    # ------------------------------------------------------

    if cmd == "BOT" and parts == ["ORDER"]:
        clear_session(uid)
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        set_session(uid, "WAIT_COLOR", {})
        reply_message(
            reply_token,
            [quick("🎨 เลือกสี:", [(c, f"BOT:COLOR:{c}") for c in colors])],
        )
        return

    if cmd == "BOT" and parts[:1] == ["COLOR"]:
        if state != "WAIT_COLOR":
            send_menu(reply_token)
            return

        color = parts[1]
        sizes = get_available_sizes(color)

        set_session(uid, "WAIT_SIZE", {"color": color})

        reply_message(
            reply_token,
            [
                quick(
                    f"👖 {color}\nเลือกไซส์:",
                    [(f"{s} • {get_price(color, s)}฿", f"BOT:SIZE:{color}:{s}") for s in sizes],
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

        set_session(uid, "WAIT_QTY", {"color": color, "size": size})

        reply_message(
            reply_token,
            [
                quick(
                    f"📦 {color} / {size}\nเลือกจำนวน:",
                    [(str(i), f"BOT:QTY:{color}:{size}:{i}") for i in range(1, min(stock, 5) + 1)],
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

        price = get_price(color, size)
        total = price * qty

        set_session(
            uid,
            "WAIT_CONFIRM_ITEM",
            {"color": color, "size": size, "qty": qty, "price": price, "total": total},
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

    if state == "WAIT_NAME":
        data["name"] = text
        set_session(uid, "WAIT_PHONE", data)
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์เบอร์โทร (10 หลัก):"}])
        return

    if state == "WAIT_PHONE":
        data["phone"] = text
        set_session(uid, "WAIT_ADDRESS", data)
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ที่อยู่จัดส่ง:"}])
        return

    if state == "WAIT_ADDRESS":
        data["address"] = text
        data["confirm_token"] = gen_token()

        set_session(uid, "WAIT_FINAL_CONFIRM", data)

        reply_message(
            reply_token,
            [
                quick(
                    f"📦 ตรวจสอบก่อนยืนยัน\n{data['color']} / {data['size']}\n"
                    f"{data['qty']} ตัว\nรวม {data['total']} บาท\n\n"
                    f"{data['name']}\n{data['phone']}\n{data['address']}",
                    [("✅ ยืนยันคำสั่งซื้อ", "BOT:FINAL_CONFIRM")],
                )
            ],
        )
        return

    if cmd == "BOT" and parts == ["FINAL_CONFIRM"]:
        if state != "WAIT_FINAL_CONFIRM":
            send_menu(reply_token)
            return

        ok, remain = deduct_stock(data["color"], data["size"], data["qty"])
        if not ok:
            clear_session(uid)
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        order_id = create_order(uid, data)
        notify_admin_context(uid, {**data, "order_id": order_id})

        clear_session(uid)

        reply_message(
            reply_token,
            [
                quick(
                    f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}",
                    [],
                    include_admin=True,
                    include_menu=True,
                )
            ],
        )
        return

    send_menu(reply_token)


# ----------------------------------------------------------
# ENTRY
# ----------------------------------------------------------

def handle_event(event):

    uid = event["source"]["userId"]
    reply_token = event["replyToken"]

    if event.get("type") == "message":
        msg = event.get("message", {})
        if msg.get("type") == "text":
            handle(uid, reply_token, msg.get("text", "").strip())

    if event.get("type") == "postback":
        handle(uid, reply_token, event["postback"]["data"])
