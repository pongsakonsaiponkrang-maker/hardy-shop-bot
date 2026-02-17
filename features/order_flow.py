# ==========================================================
# HARDY ORDER FLOW - PRODUCTION FINAL (Render Free Friendly)
# - Postback QuickReply (ไม่โชว์ BOT:... ในแชต)
# - Clean state machine (State-first)
# - "คุยกับเจ้าหน้าที่" ตัด flow อัตโนมัติ + ส่ง context ให้แอดมิน
# - ปุ่ม "กลับสู่เมนู"
# - Admin command ปิดออเดอร์ (CLOSE:<ORDER_ID>)
# - ไม่แสดง stock ให้ลูกค้า
# ==========================================================

from __future__ import annotations
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

# ----------------------------
# UI Helpers
# ----------------------------

def quick(text: str, buttons: list[tuple[str, str]], include_admin=True, include_menu=True):
    """
    QuickReply using postback so payload won't appear in chat.
    buttons: [(label, payload_data)]
    """
    items = list(buttons)

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

def send_menu(reply_token: str):
    reply_message(
        reply_token,
        [
            quick(
                "👖 HARDY\nเลือกเมนู:",
                [
                    ("🛒 สั่งซื้อ", "BOT:ORDER"),
                    ("🎨 ดูสีที่มี", "BOT:COLORS"),
                ],
                include_admin=True,
                include_menu=False,
            )
        ],
    )

def parse_payload(text: str):
    t = (text or "").strip()
    if not t.startswith("BOT:"):
        return None, []
    parts = t.split(":")
    return parts[0], parts[1:]

# ----------------------------
# Validators
# ----------------------------

def valid_name(s: str) -> bool:
    return len((s or "").strip()) >= 3

def valid_phone_10(s: str) -> bool:
    p = (s or "").strip().replace("-", "").replace(" ", "")
    return len(p) == 10 and p.isdigit() and p.startswith("0")

def valid_address(s: str) -> bool:
    return len((s or "").strip()) >= 10

# ==========================================================
# Main handler
# ==========================================================

def handle(uid: str, reply_token: str, text: str):
    text = (text or "").strip()

    # โหลด session
    session = get_session(uid) or {}
    state = session.get("state", "IDLE")
    data = session.get("data", {}) or {}

    # ------------------------------------------------------
    # Admin: close order by text command "CLOSE:<ORDER_ID>"
    # (ให้แอดมินพิมพ์เองในแชตกับบอท)
    # ------------------------------------------------------
    if is_admin_uid(uid) and text.upper().startswith("CLOSE:"):
        order_id = text.split(":", 1)[1].strip()
        if not order_id:
            reply_message(reply_token, [{"type": "text", "text": "รูปแบบคำสั่ง: CLOSE:HDxxxx"}])
            return
        ok = admin_close_order(order_id)
        reply_message(
            reply_token,
            [{"type": "text", "text": f"{'✅' if ok else '❌'} ปิดออเดอร์: {order_id}"}],
        )
        return

    # ------------------------------------------------------
    # Reset / Menu keyword (พิมพ์เองก็ได้)
    # ------------------------------------------------------
    if text.lower() in ["เมนู", "menu", "hi", "hello", "start"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # ------------------------------------------------------
    # STATE FIRST (กัน flow leak)
    # ------------------------------------------------------
    if state == "ADMIN_CHAT":
        # ลูกค้ากำลังคุยกับเจ้าหน้าที่
        forward_to_admin(uid, text)
        reply_message(
            reply_token,
            [
                quick(
                    "ส่งถึงเจ้าหน้าที่แล้ว ✅\n(พิมพ์ต่อได้เลย หรือกดกลับเมนู)",
                    [],
                    include_admin=False,
                    include_menu=True,
                )
            ],
        )
        return

    if state == "WAIT_NAME":
        if not valid_name(text):
            reply_message(reply_token, [{"type": "text", "text": "ชื่อ-นามสกุลสั้นเกินไป ลองใหม่ครับ"}])
            return
        data["name"] = text.strip()
        set_session(uid, "WAIT_PHONE", data)
        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์เบอร์โทร (10 หลัก ขึ้นต้น 0):"}])
        return

    if state == "WAIT_PHONE":
        if not valid_phone_10(text):
            reply_message(reply_token, [{"type": "text", "text": "เบอร์ไม่ถูกต้อง ❌\nต้อง 10 หลักและขึ้นต้น 0\nพิมพ์ใหม่ครับ:"}])
            return
        data["phone"] = text.strip().replace("-", "").replace(" ", "")
        set_session(uid, "WAIT_ADDRESS", data)
        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์ที่อยู่จัดส่ง (อย่างน้อย 10 ตัวอักษร):"}])
        return

    if state == "WAIT_ADDRESS":
        if not valid_address(text):
            reply_message(reply_token, [{"type": "text", "text": "ที่อยู่สั้นเกินไป ลองใหม่ครับ"}])
            return

        data["address"] = text.strip()
        data["confirm_token"] = gen_token()
        data["payment_status"] = "PENDING"
        data["confirm_lock"] = False

        set_session(uid, "WAIT_FINAL_CONFIRM", data)

        reply_message(
            reply_token,
            [
                quick(
                    "📦 ตรวจสอบก่อนยืนยัน\n\n"
                    f"สินค้า: {data.get('color')} / {data.get('size')}\n"
                    f"จำนวน: {data.get('qty')} ตัว\n"
                    f"รวม: {data.get('total')} บาท\n\n"
                    f"ผู้รับ: {data.get('name')}\n"
                    f"โทร: {data.get('phone')}\n"
                    f"ที่อยู่: {data.get('address')}\n\n"
                    "กดปุ่มเพื่อยืนยันคำสั่งซื้อ",
                    [("✅ ยืนยันคำสั่งซื้อ", "BOT:FINAL_CONFIRM")],
                    include_admin=True,
                    include_menu=True,
                )
            ],
        )
        return

    # ------------------------------------------------------
    # COMMAND HANDLING (postback data)
    # ------------------------------------------------------
    cmd, parts = parse_payload(text)

    # --- MENU ---
    if cmd == "BOT" and parts == ["MENU"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # --- COLORS list ---
    if cmd == "BOT" and parts == ["COLORS"]:
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "ตอนนี้สินค้าหมด ❌"}])
            return
        reply_message(reply_token, [{"type": "text", "text": "🎨 สีที่มี: " + ", ".join(colors)}])
        send_menu(reply_token)
        return

    # --- ADMIN entry (ตัด flow + ส่ง context) ---
    if cmd == "BOT" and parts == ["ADMIN"]:
        last_context = data.copy() if isinstance(data, dict) else {}
        clear_session(uid)  # ตัด flow อัตโนมัติ

        # ส่ง context ให้แอดมิน (ถ้ามี)
        notify_admin_context(uid, last_context)

        # เข้าโหมดคุยเจ้าหน้าที่
        set_session(uid, "ADMIN_CHAT", {"context": last_context})
        reply_message(
            reply_token,
            [
                quick(
                    "👩‍💼 เชื่อมต่อเจ้าหน้าที่แล้ว\nพิมพ์ข้อความที่ต้องการได้เลย",
                    [],
                    include_admin=False,
                    include_menu=True,
                )
            ],
        )
        return

    # --- START ORDER ---
    if cmd == "BOT" and parts == ["ORDER"]:
        clear_session(uid)
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "ตอนนี้สินค้าหมด ❌"}])
            return

        set_session(uid, "WAIT_COLOR", {})
        reply_message(
            reply_token,
            [quick("🎨 เลือกสีที่ต้องการ", [(c, f"BOT:COLOR:{c}") for c in colors])],
        )
        return

    # --- COLOR ---
    if cmd == "BOT" and parts[:1] == ["COLOR"]:
        if state != "WAIT_COLOR":
            send_menu(reply_token)
            return
        if len(parts) != 2:
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
                    f"👖 {color}\nเลือกไซส์:",
                    [(f"Size {s} • {get_price(color, s)}฿", f"BOT:SIZE:{color}:{s}") for s in sizes],
                )
            ],
        )
        return

    # --- SIZE ---
    if cmd == "BOT" and parts[:1] == ["SIZE"]:
        if state != "WAIT_SIZE":
            send_menu(reply_token)
            return
        if len(parts) != 3:
            send_menu(reply_token)
            return

        color, size = parts[1], parts[2]

        stock = get_stock(color, size)
        if stock <= 0:
            reply_message(reply_token, [{"type": "text", "text": "ไซส์นี้หมด ❌"}])
            return

        set_session(uid, "WAIT_QTY", {"color": color, "size": size})

        max_qty = min(stock, 5)  # ไม่โชว์ stock แต่จำกัดปุ่มสูงสุด 5
        reply_message(
            reply_token,
            [
                quick(
                    f"📦 {color} / {size}\nเลือกจำนวน:",
                    [(str(i), f"BOT:QTY:{color}:{size}:{i}") for i in range(1, max_qty + 1)],
                )
            ],
        )
        return

    # --- QTY ---
    if cmd == "BOT" and parts[:1] == ["QTY"]:
        if state != "WAIT_QTY":
            send_menu(reply_token)
            return
        if len(parts) != 4:
            send_menu(reply_token)
            return

        color, size, qty_str = parts[1], parts[2], parts[3]
        qty = safe_int(qty_str, 0)
        if qty <= 0:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        if qty > stock:
            reply_message(reply_token, [{"type": "text", "text": "จำนวนเกินสต๊อก ❌ กรุณาเลือกใหม่"}])
            return

        price = get_price(color, size)
        total = qty * price

        set_session(
            uid,
            "WAIT_CONFIRM_ITEM",
            {"color": color, "size": size, "qty": qty, "price": price, "total": total},
        )

        reply_message(
            reply_token,
            [
                quick(
                    "🧾 สรุปสินค้า\n\n"
                    f"สี: {color}\n"
                    f"ไซส์: {size}\n"
                    f"จำนวน: {qty} ตัว\n"
                    f"รวมทั้งหมด: {total} บาท\n\n"
                    "กดยืนยันเพื่อกรอกข้อมูลจัดส่ง",
                    [("✅ ยืนยันสินค้า", "BOT:ITEM_OK")],
                )
            ],
        )
        return

    # --- ITEM OK -> ask name ---
    if cmd == "BOT" and parts == ["ITEM_OK"]:
        if state != "WAIT_CONFIRM_ITEM":
            send_menu(reply_token)
            return

        set_session(uid, "WAIT_NAME", data)
        reply_message(reply_token, [{"type": "text", "text": "กรุณาพิมพ์ชื่อ-นามสกุลผู้รับ:"}])
        return

    # --- FINAL CONFIRM ---
    if cmd == "BOT" and parts == ["FINAL_CONFIRM"]:
        if state != "WAIT_FINAL_CONFIRM":
            # session หลุด/หมดอายุ
            reply_message(
                reply_token,
                [quick("Session หมดอายุ กรุณาเริ่มสั่งซื้อใหม่", [("🛒 สั่งซื้อใหม่", "BOT:ORDER")])],
            )
            return

        # กันกดซ้ำในช่วง retry
        if data.get("confirm_lock") is True:
            reply_message(reply_token, [{"type": "text", "text": "ระบบกำลังดำเนินการ ✅"}])
            return

        data["confirm_lock"] = True
        set_session(uid, "WAIT_FINAL_CONFIRM", data)

        ok, remain = deduct_stock(data["color"], data["size"], int(data["qty"]))
        if not ok:
            clear_session(uid)
            reply_message(
                reply_token,
                [quick("สต๊อกไม่พอ ❌\nกรุณาเริ่มใหม่", [("🛒 สั่งซื้อ", "BOT:ORDER")])],
            )
            return

        order_id = create_order(uid, data)

        # แจ้งแอดมินพร้อม context + วิธีปิดออเดอร์
        notify_admin_context(uid, {**data, "order_id": order_id, "remain": remain})

        clear_session(uid)

        reply_message(
            reply_token,
            [
                quick(
                    "รับออเดอร์แล้ว ✅\n"
                    f"ORDER ID: {order_id}\n"
                    "เจ้าหน้าที่จะติดต่อกลับเพื่อปิดการขาย",
                    [("🏠 กลับสู่เมนู", "BOT:MENU")],
                    include_admin=True,
                    include_menu=False,
                )
            ],
        )
        return

    # DEFAULT
    send_menu(reply_token)

# ==========================================================
# Entry: supports message + postback
# ==========================================================

def handle_event(event: dict):
    try:
        uid = event["source"]["userId"]
        reply_token = event["replyToken"]

        # Text message
        if event.get("type") == "message":
            msg = event.get("message", {})
            if msg.get("type") != "text":
                return
            text = (msg.get("text") or "").strip()
            handle(uid, reply_token, text)
            return

        # Postback (QuickReply)
        if event.get("type") == "postback":
            data = (event.get("postback", {}) or {}).get("data", "")
            handle(uid, reply_token, data)
            return

    except Exception as e:
        print("ORDER FLOW ERROR:", e)
