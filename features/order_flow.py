# features/order_flow.py

from typing import Dict, Any, List, Tuple

from integrations.line_api import (
    reply_message,
    push_message,
    text_message,
    quick_reply_message,
    buttons_message,
    carousel_message,
    flex_product_card,
    flex_order_summary,
)
from services.stock_service import (
    get_all_colors,
    get_sizes_by_color,
    get_stock,
    get_price,
    deduct_stock,
)
from services.session_service import get_session, set_session, clear_session
from services.order_service import create_order
from services.admin_service import notify_new_order, forward_customer_message
from core.utils import safe_int
from core.config import ADMIN_USER_IDS


# -------------------
# COMMAND TOKENS
# -------------------
CMD_ORDER_START = "BOT:ORDER_START"
CMD_MENU = "BOT:MENU"
CMD_CHAT_ADMIN = "BOT:CHAT_ADMIN"
CMD_BACK_TO_BOT = "BOT:BACK_TO_BOT"

CMD_COLOR_PREFIX = "BOT:COLOR:"
CMD_SIZE_PREFIX = "BOT:SIZE:"
CMD_QTY_PREFIX = "BOT:QTY:"
CMD_CONFIRM = "BOT:CONFIRM"
CMD_CANCEL = "BOT:CANCEL"

ADMIN_REPLY_TO_PREFIX = "ADMIN_REPLY_TO:"
ADMIN_END_CHAT_PREFIX = "ADMIN_END_CHAT:"
ADMIN_HELP = "ADMIN_HELP"


# -------------------
# ENTRY
# -------------------

def handle_event(ev: Dict[str, Any]) -> None:
    """
    Called from app.py
    """
    if ev.get("type") != "message":
        return
    msg = ev.get("message", {})
    if msg.get("type") != "text":
        return

    uid = ev.get("source", {}).get("userId", "")
    reply_token = ev.get("replyToken", "")
    text = (msg.get("text") or "").strip()

    if not uid or not reply_token:
        return

    handle_text(uid, reply_token, text)


def handle_text(uid: str, reply_token: str, text: str) -> None:
    s = get_session(uid)
    state = s["state"]
    data = s["data"] or {}
    mode = data.get("mode", "BOT")  # BOT | ADMIN_CHAT | ADMIN_TOOL

    # ------------- ADMIN TOOL (แอดมินคุมการตอบ) -------------
    if text.startswith(ADMIN_REPLY_TO_PREFIX):
        customer_uid = text.replace(ADMIN_REPLY_TO_PREFIX, "", 1).strip()
        data = {"mode": "ADMIN_TOOL", "reply_to": customer_uid}
        set_session(uid, "ADMIN_REPLY", data)
        return reply_message(reply_token, [
            quick_reply_message(
                f"🟢 ตั้งค่าแล้ว: จะตอบลูกค้า UID\n{customer_uid}\n\nพิมพ์ข้อความตอบกลับได้เลย (โหมดแอดมินอนุญาตให้พิมพ์)",
                [("ยกเลิก", CMD_BACK_TO_BOT)]
            )
        ])

    if text.startswith(ADMIN_END_CHAT_PREFIX):
        customer_uid = text.replace(ADMIN_END_CHAT_PREFIX, "", 1).strip()
        # ปิดโหมดแชทของลูกค้า
        cust = get_session(customer_uid)
        cust_data = cust["data"] or {}
        cust_data["mode"] = "BOT"
        set_session(customer_uid, "IDLE", cust_data)
        return reply_message(reply_token, [text_message(f"ปิดแชทลูกค้า {customer_uid} แล้ว ✅")])

    if text == ADMIN_HELP:
        return reply_message(reply_token, [
            text_message(
                "ADMIN HELP\n"
                "- เมื่อมีลูกค้าทัก จะมีปุ่ม 'ตอบคนนี้'\n"
                "- กดแล้วพิมพ์ข้อความตอบกลับ\n"
                "- กด 'จบแชทคนนี้' เพื่อคืนโหมดให้บอท"
            )
        ])

    if mode == "ADMIN_TOOL" and state == "ADMIN_REPLY":
        # แอดมินพิมพ์ตอบลูกค้า
        customer_uid = data.get("reply_to", "")
        if not customer_uid:
            clear_session(uid)
            return reply_message(reply_token, [text_message("ไม่พบลูกค้าที่จะตอบ ❌")])

        # ส่งให้ลูกค้า
        try:
            push_message(customer_uid, [text_message(f"👤 แอดมิน: {text}")])
        except Exception:
            pass

        return reply_message(reply_token, [
            quick_reply_message(
                "ส่งให้ลูกค้าแล้ว ✅ (พิมพ์ต่อได้ หรือกดจบ)",
                [("จบ", CMD_BACK_TO_BOT)]
            )
        ])

    # ------------- MODE: ลูกค้าคุยแอดมิน -------------
    if text == CMD_CHAT_ADMIN or text == "คุยกับแอดมิน":
        data["mode"] = "ADMIN_CHAT"
        set_session(uid, "ADMIN_CHAT", data)
        forward_customer_message(uid, "ลูกค้าเริ่มคุยกับแอดมิน")
        return reply_message(reply_token, [
            quick_reply_message(
                "🔴 เข้าสู่โหมดคุยแอดมินแล้ว\nพิมพ์ข้อความถึงแอดมินได้เลย\n(กด 'กลับไปสั่งกับบอท' เพื่อกลับ)",
                [("กลับไปสั่งกับบอท", CMD_BACK_TO_BOT)]
            )
        ])

    if mode == "ADMIN_CHAT":
        if text == CMD_BACK_TO_BOT:
            data["mode"] = "BOT"
            set_session(uid, "IDLE", data)
            return reply_message(reply_token, [main_menu_message()])
        # forward ทุกข้อความไป admin
        forward_customer_message(uid, text)
        return reply_message(reply_token, [
            quick_reply_message(
                "ส่งถึงแอดมินแล้ว ✅",
                [("กลับไปสั่งกับบอท", CMD_BACK_TO_BOT)]
            )
        ])

    # ------------- BOT MENU -------------
    if text in [CMD_MENU, "เมนู", CMD_BACK_TO_BOT]:
        clear_session(uid)
        return reply_message(reply_token, [main_menu_message()])

    if text == CMD_ORDER_START or text == "สั่งซื้อ":
        clear_session(uid)
        set_session(uid, "ASK_COLOR", {"mode": "BOT"})
        return reply_message(reply_token, [colors_message()])

    if text == CMD_CANCEL:
        clear_session(uid)
        return reply_message(reply_token, [main_menu_message()])

    # ------------- Admin command ในโหมดบอท -------------
    # (เพื่อความง่าย: ถ้า uid อยู่ใน ADMIN_USER_IDS ให้พิมพ์สต๊อกได้)
    if uid in ADMIN_USER_IDS and text.startswith("สต๊อก "):
        parts = text.split()
        if len(parts) == 3:
            c, sz = parts[1], parts[2]
            st = get_stock(c, sz)
            pr = get_price(c, sz)
            return reply_message(reply_token, [text_message(f"{c} {sz}\nStock: {st}\nPrice: {pr}")])

    # ------------- FLOW: ASK_COLOR -------------
    if state == "ASK_COLOR":
        colors = get_all_colors(hide_out_of_stock=True)
        picked = _parse_value(text, CMD_COLOR_PREFIX)
        if not picked or picked not in colors:
            return reply_message(reply_token, [colors_message("เลือกสีจากปุ่มด้านล่างเท่านั้น")])

        data["color"] = picked
        set_session(uid, "ASK_SIZE", data)
        return reply_message(reply_token, [sizes_message(picked)])

    # ------------- FLOW: ASK_SIZE -------------
    if state == "ASK_SIZE":
        color = data.get("color", "")
        sizes = get_sizes_by_color(color, hide_out_of_stock=True)
        picked = _parse_value(text, CMD_SIZE_PREFIX)
        if not picked or picked not in sizes:
            return reply_message(reply_token, [sizes_message(color, "เลือกไซส์จากปุ่มด้านล่างเท่านั้น")])

        price = get_price(color, picked)
        stock = get_stock(color, picked)
        if price <= 0 or stock <= 0:
            return reply_message(reply_token, [sizes_message(color, "รายการนี้ยังไม่พร้อมขาย (ราคา/สต๊อกผิด) ❌")])

        data["size"] = picked
        data["price"] = int(price)
        set_session(uid, "ASK_QTY", data)

        # Flex โชว์ราคา + สต๊อก
        return reply_message(reply_token, [
            flex_product_card("HARDY", color, picked, int(price), int(stock)),
            qty_message(color, picked),
        ])

    # ------------- FLOW: ASK_QTY -------------
    if state == "ASK_QTY":
        color = data.get("color", "")
        size = data.get("size", "")
        stock = get_stock(color, size)

        picked_qty = _parse_value(text, CMD_QTY_PREFIX)
        if picked_qty is None:
            return reply_message(reply_token, [qty_message(color, size, "เลือกจำนวนจากปุ่มเท่านั้น")])

        qty = safe_int(picked_qty, 0)
        if qty <= 0 or qty > stock:
            return reply_message(reply_token, [qty_message(color, size, f"คงเหลือ {stock} ตัว เลือกใหม่")])

        data["qty"] = qty
        set_session(uid, "ASK_NAME", data)

        # ชื่อ/เบอร์/ที่อยู่ ถ้าจะ “ปุ่มล้วนจริง ๆ” ต้องใช้ LINE LIFF/Forms
        # ที่นี่ให้ลูกค้าพิมพ์เฉพาะข้อมูลจัดส่ง (จำเป็น) แต่ยังมีปุ่มควบคุม
        return reply_message(reply_token, [
            quick_reply_message("พิมพ์ชื่อ-นามสกุลผู้รับ:", [("ยกเลิก", CMD_CANCEL)])
        ])

    # ------------- ASK_NAME / PHONE / ADDRESS (ข้อมูลจัดส่งจำเป็นต้องพิมพ์) -------------
    if state == "ASK_NAME":
        if len(text) < 2:
            return reply_message(reply_token, [text_message("ชื่อสั้นเกินไป ❌ พิมพ์ใหม่อีกครั้ง")])
        data["name"] = text
        set_session(uid, "ASK_PHONE", data)
        return reply_message(reply_token, [quick_reply_message("พิมพ์เบอร์โทร (10 หลัก):", [("ยกเลิก", CMD_CANCEL)])])

    if state == "ASK_PHONE":
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) != 10:
            return reply_message(reply_token, [text_message("เบอร์ไม่ถูกต้อง ❌ (ต้องเป็น 10 หลัก) พิมพ์ใหม่")])
        data["phone"] = digits
        set_session(uid, "ASK_ADDRESS", data)
        return reply_message(reply_token, [quick_reply_message("พิมพ์ที่อยู่จัดส่ง:", [("ยกเลิก", CMD_CANCEL)])])

    if state == "ASK_ADDRESS":
        if len(text.strip()) < 10:
            return reply_message(reply_token, [text_message("ที่อยู่สั้นไป ❌ พิมพ์ให้ละเอียดขึ้น")])
        data["address"] = text.strip()
        set_session(uid, "CONFIRM", data)
        return reply_message(reply_token, [confirm_message(data)])

    # ------------- CONFIRM -------------
    if state == "CONFIRM":
        if text != CMD_CONFIRM:
            return reply_message(reply_token, [confirm_message(data, "กดยืนยันจากปุ่มเท่านั้น")])

        # ตัดสต๊อกก่อนสร้างออเดอร์
        ok, remaining, _low = deduct_stock(data["color"], data["size"], int(data["qty"]))
        if not ok:
            set_session(uid, "ASK_QTY", data)
            return reply_message(reply_token, [qty_message(data["color"], data["size"], "สต๊อกเปลี่ยนระหว่างทำรายการ ❌ เลือกจำนวนใหม่")])

        # สร้างออเดอร์
        data["user_id"] = uid
        order_id = create_order(data)

        # แจ้งแอดมิน
        notify_new_order(order_id, data, remaining)

        total = int(data["qty"]) * int(data["price"])
        clear_session(uid)

        return reply_message(reply_token, [
            flex_order_summary(order_id, data, total),
            main_menu_message()
        ])

    # default
    return reply_message(reply_token, [main_menu_message()])


# -------------------
# UI MESSAGES
# -------------------

def main_menu_message():
    return buttons_message(
        "HARDY",
        "เลือกเมนู",
        [
            ("สั่งซื้อสินค้า", CMD_ORDER_START),
            ("คุยกับแอดมิน", CMD_CHAT_ADMIN),
            ("เมนู", CMD_MENU),
        ],
        alt_text="HARDY MENU"
    )


def colors_message(note: str = ""):
    colors = get_all_colors(hide_out_of_stock=True)

    if not colors:
        return text_message("ขออภัย ตอนนี้สินค้าหมดสต๊อกทั้งหมด ❌")

    # <=4 ใช้ Buttons
    if len(colors) <= 4:
        actions = [(c, f"{CMD_COLOR_PREFIX}{c}") for c in colors]
        text = "เลือกสี (เฉพาะมีสต๊อก)"
        if note:
            text = f"{note}\n\n{text}"
        return buttons_message("เลือกสี", text, actions, alt_text="Choose color")

    # >4 ใช้ Carousel
    columns = []
    for c in colors:
        columns.append({
            "title": c,
            "text": "พร้อมส่ง" ,
            "actions": [("เลือก", f"{CMD_COLOR_PREFIX}{c}")],
        })

    if note:
        # ส่ง note เป็น text แยก จะชัดกว่า
        return [text_message(note), carousel_message("เลือกสี", columns)]

    return carousel_message("เลือกสี", columns)


def sizes_message(color: str, note: str = ""):
    sizes = get_sizes_by_color(color, hide_out_of_stock=True)
    if not sizes:
        return text_message("สีนี้หมดทุกไซส์ ❌ กลับไปเลือกสีใหม่")

    # ทำเป็น Carousel เพื่อโชว์ “ราคาในปุ่ม” ได้เยอะกว่า buttons
    columns = []
    for s in sizes:
        price = get_price(color, s)
        stock = get_stock(color, s)
        columns.append({
            "title": f"{color}",
            "text": f"{s} | {price:,}฿ | stock {stock}",
            "actions": [("เลือกไซส์นี้", f"{CMD_SIZE_PREFIX}{s}")],
        })

    if note:
        return [text_message(note), carousel_message("เลือกไซส์", columns)]

    return carousel_message("เลือกไซส์", columns)


def qty_message(color: str, size: str, note: str = ""):
    stock = get_stock(color, size)
    max_qty = min(stock, 13)  # quick reply รองรับได้หลายปุ่มกว่า

    items = [(str(i), f"{CMD_QTY_PREFIX}{i}") for i in range(1, max_qty + 1)]
    items.append(("ยกเลิก", CMD_CANCEL))

    text = f"เลือกจำนวน (คงเหลือ {stock})"
    if note:
        text = f"{note}\n\n{text}"
    return quick_reply_message(text, items)


def confirm_message(data: Dict[str, Any], note: str = ""):
    qty = int(data["qty"])
    price = int(data["price"])
    total = qty * price

    text = (
        "🧾 ยืนยันออเดอร์\n"
        f"- Color: {data['color']}\n"
        f"- Size: {data['size']}\n"
        f"- Price: {price:,} THB\n"
        f"- Qty: {qty}\n"
        f"- Total: {total:,} THB\n\n"
        "กดปุ่มเพื่อยืนยัน"
    )
    if note:
        text = f"{note}\n\n{text}"

    return buttons_message(
        "ยืนยันออเดอร์",
        text,
        [
            ("✅ ยืนยัน", CMD_CONFIRM),
            ("❌ ยกเลิก", CMD_CANCEL),
        ],
        alt_text="Confirm order"
    )


# -------------------
# helpers
# -------------------

def _parse_value(text: str, prefix: str):
    if not text.startswith(prefix):
        return None
    return text[len(prefix):].strip()