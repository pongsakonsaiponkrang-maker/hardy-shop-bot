#!/usr/bin/env python3
# ==========================================================
# HARDY LINE SHOP BOT - HARDY PRO (Production) + Dynamic Price
# Features:
# - Quick Reply Menu (no typing errors)
# - Session stored in Google Sheet (survive restart)
# - Stock control (block oversell + deduct stock)
# - Dynamic price from HARDY_STOCK (price column)
# - Admin push notification (multiple admins)
# - Orders stored in Google Sheet
# ==========================================================

import os
import json
import time
import hmac
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

import requests
from flask import Flask, request, abort

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv


# ---------- LOAD ENV ----------
load_dotenv()
APP_TZ = timezone(timedelta(hours=7))

# ---------- ENV ----------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()

SHEET_ID = os.getenv("SHEET_ID", "").strip()
ORDERS_SHEET_NAME = os.getenv("ORDERS_SHEET_NAME", "HARDY_ORDER").strip()
SESSIONS_SHEET_NAME = os.getenv("SESSIONS_SHEET_NAME", "HARDY_SESSION").strip()
STOCK_SHEET_NAME = os.getenv("STOCK_SHEET_NAME", "HARDY_STOCK").strip()

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# Admins: comma-separated userIds
ADMIN_USER_IDS = [x.strip() for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()]

COLORS = ["Dark Coffee", "Navy"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
LOW_STOCK_ALERT = int(os.getenv("LOW_STOCK_ALERT", "3").strip() or "3")  # แจ้งเตือนสต๊อกต่ำ (default 3)

# ---------- APP ----------
app = Flask(__name__)

_gc = None
_sheet_orders = None
_sheet_sessions = None
_sheet_stock = None


# ---------- UTILS ----------
def now_dt() -> datetime:
    return datetime.now(APP_TZ)

def now_str() -> str:
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")

def safe_int(s: Any, default: int = 0) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return default

def is_admin(uid: str) -> bool:
    return uid in ADMIN_USER_IDS


# ---------- GOOGLE SHEET ----------
def load_sheets():
    global _gc, _sheet_orders, _sheet_sessions, _sheet_stock

    if _gc:
        return

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON in env")
    if not SHEET_ID:
        raise RuntimeError("Missing SHEET_ID in env")

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    _gc = gspread.authorize(creds)
    sh = _gc.open_by_key(SHEET_ID)

    _sheet_orders = sh.worksheet(ORDERS_SHEET_NAME)
    _sheet_sessions = sh.worksheet(SESSIONS_SHEET_NAME)
    _sheet_stock = sh.worksheet(STOCK_SHEET_NAME)


# ---------- LINE HELPERS ----------
def verify_signature(body: bytes, signature: str) -> bool:
    mac = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)

def line_reply(reply_token: str, messages: List[Dict[str, Any]]) -> None:
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"replyToken": reply_token, "messages": messages}
    requests.post(url, headers=headers, json=payload, timeout=15)

def line_push(to_user_id: str, messages: List[Dict[str, Any]]) -> None:
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"to": to_user_id, "messages": messages}
    requests.post(url, headers=headers, json=payload, timeout=15)

def msg_text(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}

def quick_reply_message(text: str, items: List[Tuple[str, str]]) -> Dict[str, Any]:
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {"type": "action", "action": {"type": "message", "label": label, "text": send_text}}
                for (label, send_text) in items
            ]
        }
    }


# ---------- STOCK + PRICE ----------
def stock_get_record(color: str, size: str) -> Dict[str, Any]:
    """
    อ่านทั้ง record จาก HARDY_STOCK โดยต้องมี columns: color, size, stock, price
    """
    load_sheets()
    records = _sheet_stock.get_all_records()
    for r in records:
        if str(r.get("color", "")).strip() == color and str(r.get("size", "")).strip() == size:
            return r
    return {}

def stock_get(color: str, size: str) -> int:
    r = stock_get_record(color, size)
    return safe_int(r.get("stock", 0), 0)

def price_get(color: str, size: str) -> int:
    r = stock_get_record(color, size)
    return safe_int(r.get("price", 0), 0)

def stock_set(color: str, size: str, new_stock: int) -> bool:
    """
    อัปเดต stock ที่คอลัมน์ 'stock' (หา index จาก header)
    """
    load_sheets()
    values = _sheet_stock.get_all_values()
    if not values:
        return False

    header = [h.strip() for h in values[0]]
    try:
        col_color = header.index("color") + 1
        col_size = header.index("size") + 1
        col_stock = header.index("stock") + 1
    except ValueError:
        # header ไม่ตรง
        return False

    for row_i in range(2, len(values) + 1):
        row = values[row_i - 1]
        c = row[col_color - 1].strip() if len(row) >= col_color else ""
        s = row[col_size - 1].strip() if len(row) >= col_size else ""
        if c == color and s == size:
            _sheet_stock.update_cell(row_i, col_stock, int(new_stock))
            return True

    # ถ้าไม่เจอ record ให้ append (จะใส่ price=0 ไว้ก่อน)
    # NOTE: แนะนำให้คุณสร้างรายการในชีทให้ครบอยู่แล้ว เพื่อไม่ให้ price=0
    new_row = [""] * len(header)
    new_row[col_color - 1] = color
    new_row[col_size - 1] = size
    new_row[col_stock - 1] = str(int(new_stock))
    _sheet_stock.append_row(new_row)
    return True

def stock_deduct(color: str, size: str, qty: int) -> Tuple[bool, int]:
    """
    Return (success, remaining_stock)
    """
    current = stock_get(color, size)
    if qty <= 0:
        return False, current
    if current < qty:
        return False, current
    new_stock = current - qty
    ok = stock_set(color, size, new_stock)
    return (ok, new_stock if ok else current)


# ---------- SESSION (Stored in Sheet) ----------
def _sessions_find_row(uid: str) -> Optional[int]:
    load_sheets()
    col = _sheet_sessions.col_values(1)
    for idx, val in enumerate(col[1:], start=2):
        if val.strip() == uid:
            return idx
    return None

def session_get(uid: str) -> Dict[str, Any]:
    load_sheets()
    row = _sessions_find_row(uid)
    if not row:
        return {"state": "IDLE", "data": {}, "updated_at": 0}

    state = (_sheet_sessions.cell(row, 2).value or "IDLE").strip()
    data_json = _sheet_sessions.cell(row, 3).value or "{}"
    updated_at_str = _sheet_sessions.cell(row, 4).value or "0"

    try:
        data = json.loads(data_json)
    except Exception:
        data = {}

    updated_at = safe_int(updated_at_str, 0)

    if updated_at > 0 and (int(time.time()) - updated_at) > SESSION_TTL_SECONDS:
        session_clear(uid)
        return {"state": "IDLE", "data": {}, "updated_at": 0}

    return {"state": state, "data": data, "updated_at": updated_at}

def session_set(uid: str, state: str, data: Dict[str, Any]) -> None:
    load_sheets()
    row = _sessions_find_row(uid)
    payload = json.dumps(data, ensure_ascii=False)
    now_ts = int(time.time())

    if row:
        _sheet_sessions.update(f"A{row}:D{row}", [[uid, state, payload, str(now_ts)]])
    else:
        _sheet_sessions.append_row([uid, state, payload, str(now_ts)])

def session_clear(uid: str) -> None:
    load_sheets()
    row = _sessions_find_row(uid)
    if not row:
        return
    _sheet_sessions.update(f"A{row}:D{row}", [[uid, "IDLE", "{}", str(int(time.time()))]])


# ---------- ORDER ----------
def append_order(data: Dict[str, Any]) -> str:
    """
    บันทึกลง HARDY_ORDER (คอลัมน์เดิมของคุณ)
    time, order_id, user_id, name, phone, address, color, size, qty, amount, status
    """
    load_sheets()

    order_id = f"HD{int(time.time())}"
    qty = int(data["qty"])
    price = int(data["price"])
    amount = qty * price

    _sheet_orders.append_row(
        [
            now_str(),
            order_id,
            data["user_id"],
            data["name"],
            data["phone"],
            data["address"],
            data["color"],
            data["size"],
            qty,
            amount,
            "NEW",
        ]
    )
    return order_id


# ---------- UI MESSAGES ----------
def menu_message() -> Dict[str, Any]:
    return quick_reply_message(
        "👖 HARDY Utility Chino\nพิมพ์หรือกดปุ่มได้เลย:",
        [
            ("สั่งซื้อ", "สั่งซื้อ"),
            ("ดูสี/ไซส์", "ดูสี"),
            ("ยกเลิก", "ยกเลิก"),
        ],
    )

def show_color_message() -> Dict[str, Any]:
    return quick_reply_message("เลือกสี:", [(c, c) for c in COLORS] + [("ยกเลิก", "ยกเลิก")])

def show_size_message() -> Dict[str, Any]:
    return quick_reply_message("เลือกไซส์:", [(s, s) for s in SIZES] + [("ยกเลิก", "ยกเลิก")])

def ask_qty_message(max_qty: int) -> Dict[str, Any]:
    # สร้างปุ่มจำนวนตามสต๊อก (ไม่ให้เกิน)
    choices = []
    for n in [1, 2, 3, 4, 5]:
        if n <= max_qty:
            choices.append((str(n), str(n)))
    if not choices:
        choices = [("1", "1")]
    choices.append(("ยกเลิก", "ยกเลิก"))
    return quick_reply_message("เลือกจำนวน:", choices)

def ask_name_message() -> Dict[str, Any]:
    return msg_text("พิมพ์ชื่อ-นามสกุลผู้รับ:")

def ask_phone_message() -> Dict[str, Any]:
    return msg_text("พิมพ์เบอร์โทร (10 หลัก):")

def ask_address_message() -> Dict[str, Any]:
    return msg_text("พิมพ์ที่อยู่จัดส่ง (ละเอียด):")

def order_summary_text(data: Dict[str, Any]) -> str:
    qty = int(data["qty"])
    price = int(data["price"])
    amount = qty * price
    return (
        "🧾 สรุปออเดอร์\n"
        f"- สี: {data['color']}\n"
        f"- ไซส์: {data['size']}\n"
        f"- ราคา/ตัว: {price:,} บาท\n"
        f"- จำนวน: {qty}\n"
        f"- ยอดรวม: {amount:,} บาท\n\n"
        "ถ้าถูกต้อง พิมพ์ 'ยืนยัน' หรือกดปุ่มด้านล่าง"
    )

def confirm_message(data: Dict[str, Any]) -> Dict[str, Any]:
    return quick_reply_message(order_summary_text(data), [("ยืนยัน", "ยืนยัน"), ("ยกเลิก", "ยกเลิก")])


# ---------- ADMIN NOTIFY ----------
def notify_admin_new_order(order_id: str, data: Dict[str, Any], remaining_stock: int) -> None:
    qty = int(data["qty"])
    price = int(data["price"])
    amount = qty * price

    text = (
        "🔥 NEW ORDER (HARDY)\n\n"
        f"ORDER ID: {order_id}\n"
        f"ชื่อ: {data['name']}\n"
        f"เบอร์: {data['phone']}\n"
        f"ที่อยู่: {data['address']}\n\n"
        f"สินค้า: HARDY Utility Chino\n"
        f"สี: {data['color']} | ไซส์: {data['size']} | จำนวน: {qty}\n"
        f"ราคา/ตัว: {price:,} บาท\n"
        f"ยอด: {amount:,} บาท\n"
        f"คงเหลือสต๊อก: {remaining_stock}\n\n"
        f"เวลา: {now_str()}"
    )

    for admin_uid in ADMIN_USER_IDS:
        try:
            line_push(admin_uid, [msg_text(text)])
        except Exception:
            pass

    # low stock alert
    if remaining_stock <= LOW_STOCK_ALERT:
        warn = f"⚠ STOCK LOW: {data['color']} {data['size']} เหลือ {remaining_stock}"
        for admin_uid in ADMIN_USER_IDS:
            try:
                line_push(admin_uid, [msg_text(warn)])
            except Exception:
                pass


# ---------- VALIDATIONS ----------
def validate_phone(p: str) -> bool:
    p = "".join([ch for ch in p.strip() if ch.isdigit()])
    return len(p) == 10

def validate_address(a: str) -> bool:
    return len(a.strip()) >= 10


# ---------- FLOW ----------
def handle_text(uid: str, reply_token: str, text: str) -> None:
    text = (text or "").strip()

    # Global commands
    if text in ["เมนู", "menu", "Menu"]:
        session_clear(uid)
        return line_reply(reply_token, [menu_message()])

    if text in ["ยกเลิก", "cancel", "Cancel"]:
        session_clear(uid)
        return line_reply(reply_token, [msg_text("ยกเลิกเรียบร้อย ✅"), menu_message()])

    if text in ["ดูสี", "ดูไซส์", "สี", "ไซส์"]:
        return line_reply(reply_token, [msg_text(f"สี: {', '.join(COLORS)}\nไซส์: {', '.join(SIZES)}"), menu_message()])

    # Admin command: check stock + price
    if text.startswith("สต๊อก") and is_admin(uid):
        # "สต๊อก Dark Coffee M"
        parts = text.split()
        if len(parts) == 3:
            c, s = parts[1], parts[2]
            st = stock_get(c, s)
            pr = price_get(c, s)
            return line_reply(reply_token, [msg_text(f"STOCK: {c} {s} = {st}\nPRICE: {pr}"), menu_message()])
        return line_reply(reply_token, [msg_text("ใช้แบบนี้: สต๊อก <Color> <Size>\nเช่น: สต๊อก Navy L"), menu_message()])

    s = session_get(uid)
    state = s["state"]
    data = s["data"] or {}

    # Start order
    if text in ["สั่งซื้อ", "order", "Order"]:
        session_set(uid, "ASK_COLOR", {"user_id": uid})
        return line_reply(reply_token, [show_color_message()])

    # Color
    if state == "ASK_COLOR":
        if text not in COLORS:
            return line_reply(reply_token, [msg_text("สีไม่ถูกต้อง ❌"), show_color_message()])

        data["color"] = text
        session_set(uid, "ASK_SIZE", data)
        return line_reply(reply_token, [show_size_message()])

    # Size
    if state == "ASK_SIZE":
        if text not in SIZES:
            return line_reply(reply_token, [msg_text("ไซส์ไม่ถูกต้อง ❌"), show_size_message()])

        data["size"] = text

        st = stock_get(data["color"], data["size"])
        if st <= 0:
            session_set(uid, "ASK_SIZE", data)
            return line_reply(reply_token, [msg_text("ขออภัย ไซส์นี้สต๊อกหมด ❌\nเลือกไซส์อื่นได้เลย"), show_size_message()])

        price = price_get(data["color"], data["size"])
        if price <= 0:
            session_set(uid, "ASK_SIZE", data)
            return line_reply(reply_token, [msg_text("ขออภัย ยังไม่ได้ตั้งราคาใน HARDY_STOCK (price) ❌"), menu_message()])

        data["price"] = price  # เก็บราคาไว้ใน session
        session_set(uid, "ASK_QTY", data)
        return line_reply(reply_token, [ask_qty_message(st)])

    # Qty
    if state == "ASK_QTY":
        qty = safe_int(text, 0)
        if qty <= 0:
            st = stock_get(data.get("color", ""), data.get("size", ""))
            return line_reply(reply_token, [msg_text("จำนวนไม่ถูกต้อง ❌"), ask_qty_message(max(1, st))])

        st = stock_get(data.get("color", ""), data.get("size", ""))
        if qty > st:
            return line_reply(reply_token, [msg_text(f"สต๊อกไม่พอ ❌\nคงเหลือ {st} ตัว\nเลือกจำนวนใหม่"), ask_qty_message(st)])

        data["qty"] = qty
        session_set(uid, "ASK_NAME", data)
        return line_reply(reply_token, [ask_name_message()])

    # Name
    if state == "ASK_NAME":
        if len(text) < 2:
            return line_reply(reply_token, [msg_text("ขอชื่อ-นามสกุลอีกครั้งครับ")])
        data["name"] = text
        session_set(uid, "ASK_PHONE", data)
        return line_reply(reply_token, [ask_phone_message()])

    # Phone
    if state == "ASK_PHONE":
        if not validate_phone(text):
            return line_reply(reply_token, [msg_text("เบอร์ไม่ถูกต้อง ❌ (ต้องเป็นตัวเลข 10 หลัก)\nพิมพ์ใหม่อีกครั้ง:")])
        digits = "".join([ch for ch in text.strip() if ch.isdigit()])
        data["phone"] = digits
        session_set(uid, "ASK_ADDRESS", data)
        return line_reply(reply_token, [ask_address_message()])

    # Address
    if state == "ASK_ADDRESS":
        if not validate_address(text):
            return line_reply(reply_token, [msg_text("ที่อยู่สั้นเกินไป ❌\nพิมพ์ให้ละเอียดกว่านี้อีกนิดครับ:")])
        data["address"] = text
        session_set(uid, "CONFIRM", data)
        return line_reply(reply_token, [confirm_message(data)])

    # Confirm
    if state == "CONFIRM":
        if text != "ยืนยัน":
            return line_reply(reply_token, [msg_text("ถ้าต้องการสั่งต่อ กด 'ยืนยัน' หรือพิมพ์ 'ยกเลิก'"), confirm_message(data)])

        # Final stock deduct
        ok, remaining = stock_deduct(data["color"], data["size"], int(data["qty"]))
        if not ok:
            session_set(uid, "ASK_QTY", data)
            st = stock_get(data["color"], data["size"])
            return line_reply(
                reply_token,
                [msg_text(f"ขออภัย สต๊อกเปลี่ยนระหว่างทำรายการ ❌\nคงเหลือ {st} ตัว\nเลือกจำนวนใหม่"), ask_qty_message(st)],
            )

        order_id = append_order(data)
        session_clear(uid)

        if ADMIN_USER_IDS:
            notify_admin_new_order(order_id, data, remaining)

        qty = int(data["qty"])
        price = int(data["price"])
        amount = qty * price

        return line_reply(
            reply_token,
            [
                msg_text(
                    f"รับออเดอร์แล้ว ✅\n"
                    f"ORDER ID: {order_id}\n"
                    f"ราคา/ตัว: {price:,} บาท\n"
                    f"ยอดรวม: {amount:,} บาท\n\n"
                    "แอดมินจะติดต่อกลับเพื่อสรุปการชำระเงิน/จัดส่งครับ"
                ),
                menu_message(),
            ],
        )

    # Default
    return line_reply(reply_token, [menu_message()])


# ---------- ROUTES ----------
@app.get("/")
def home():
    return "HARDY PRO BOT RUNNING", 200

@app.post("/callback")
def callback():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, signature):
        abort(400)

    payload = request.get_json(silent=True) or {}
    events = payload.get("events", [])

    for ev in events:
        try:
            if ev.get("type") != "message":
                continue
            msg_obj = ev.get("message", {})
            if msg_obj.get("type") != "text":
                continue

            uid = ev["source"]["userId"]
            reply_token = ev["replyToken"]
            text = msg_obj.get("text", "")

            handle_text(uid, reply_token, text)
        except Exception:
            continue

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
