# app.py
import os
import json
import time
import hmac
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

import requests
from flask import Flask, request, abort

import gspread
from google.oauth2.service_account import Credentials

# ==========================================================
# HARDY PRO - LINE ORDER BOT (Production Ready)
# - LINE Webhook + Reply
# - Google Sheet Orders + Sessions
# - Simple state machine
# ==========================================================

APP_TZ = timezone(timedelta(hours=7))

# ---------- ENV ----------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()

SHEET_ID = os.getenv("SHEET_ID", "").strip()
ORDERS_SHEET_NAME = os.getenv("ORDERS_SHEET_NAME", "HARDY_ORDER").strip()
SESSIONS_SHEET_NAME = os.getenv("SESSIONS_SHEET_NAME", "SESSIONS").strip()

# ใส่ JSON ของ service account แบบ "ทั้งก้อน" ใน Render env
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# ถ้าต้องการให้แจ้งแอดมินทันทีตอนยืนยันออเดอร์
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()  # optional

# ราคา
PRICE_PER_PIECE = int(os.getenv("PRICE_PER_PIECE", "1290"))

# สินค้าที่มี
COLORS = ["Dark Coffee", "Navy"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# Session หมดอายุ (วินาที)
SESSION_TTL = int(os.getenv("SESSION_TTL", "1800"))  # 30 นาที

# ---------- APP ----------
app = Flask(__name__)

# ---------- Google Sheets Client ----------
_gc = None
_sheet_orders = None
_sheet_sessions = None

def _now_str() -> str:
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")

def _load_gspread():
    global _gc, _sheet_orders, _sheet_sessions
    if _gc and _sheet_orders and _sheet_sessions:
        return

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON")

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    _gc = gspread.authorize(creds)

    sh = _gc.open_by_key(SHEET_ID)
    _sheet_orders = sh.worksheet(ORDERS_SHEET_NAME)
    _sheet_sessions = sh.worksheet(SESSIONS_SHEET_NAME)

def _ensure_headers():
    """สร้างหัวตารางถ้ายังไม่มี (ปลอดภัยสำหรับร้านจริง)"""
    _load_gspread()

    # Orders
    orders_headers = ["DATE", "ORDER_ID", "USER_ID", "NAME", "PHONE", "ADDRESS", "COLOR", "SIZE", "QTY", "AMOUNT", "STATUS"]
    current = _sheet_orders.row_values(1)
    if not current:
        _sheet_orders.append_row(orders_headers, value_input_option="RAW")
    elif [c.strip() for c in current] != orders_headers:
        # ถ้าหัวไม่ตรง ไม่ไปแก้ทับอัตโนมัติ (กันพัง)
        pass

    # Sessions
    sess_headers = ["UPDATED_AT", "USER_ID", "STATE", "DATA_JSON", "EXPIRE_AT"]
    current2 = _sheet_sessions.row_values(1)
    if not current2:
        _sheet_sessions.append_row(sess_headers, value_input_option="RAW")

# ---------- LINE Helpers ----------
def _verify_line_signature(body: bytes, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET:
        return False
    mac = hmac.new(LINE_CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)

def _line_reply(reply_token: str, messages: List[Dict[str, Any]]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("Missing LINE_CHANNEL_ACCESS_TOKEN")

    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"replyToken": reply_token, "messages": messages}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    if r.status_code != 200:
        app.logger.error(f"LINE reply failed: {r.status_code} {r.text}")

def _line_push(to: str, messages: List[Dict[str, Any]]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    if not to:
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }
    payload = {"to": to, "messages": messages}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    if r.status_code != 200:
        app.logger.error(f"LINE push failed: {r.status_code} {r.text}")

def _msg_text(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": text}

def _quick_reply(text: str, items: List[str]) -> Dict[str, Any]:
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {"type": "message", "label": it[:20], "text": it},
                }
                for it in items
            ]
        },
    }

# ---------- Session (In-memory + Sheet persistence) ----------
# ร้านจริง: memory ช่วยเร็ว / sheet ช่วยกันหายเวลาบอทรีสตาร์ท
_sessions_cache: Dict[str, Dict[str, Any]] = {}

def _cache_get(user_id: str) -> Optional[Dict[str, Any]]:
    s = _sessions_cache.get(user_id)
    if not s:
        return None
    if s.get("expire_at", 0) < time.time():
        _sessions_cache.pop(user_id, None)
        return None
    return s

def _cache_set(user_id: str, state: str, data: Dict[str, Any], ttl: int = SESSION_TTL) -> None:
    _sessions_cache[user_id] = {
        "state": state,
        "data": data,
        "expire_at": time.time() + ttl,
    }

def _session_load_from_sheet(user_id: str) -> Optional[Dict[str, Any]]:
    _load_gspread()
    # ค้นหา USER_ID ในคอลัมน์ B (ตาม headers)
    try:
        cell = _sheet_sessions.find(user_id)
        if not cell:
            return None
        row = _sheet_sessions.row_values(cell.row)
        # ["UPDATED_AT","USER_ID","STATE","DATA_JSON","EXPIRE_AT"]
        if len(row) < 5:
            return None
        expire_at = float(row[4]) if row[4] else 0
        if expire_at < time.time():
            return None
        data = json.loads(row[3]) if row[3] else {}
        return {"state": row[2], "data": data, "expire_at": expire_at}
    except Exception:
        return None

def _session_save_to_sheet(user_id: str, state: str, data: Dict[str, Any], expire_at: float) -> None:
    _load_gspread()
    # อัปเดต/เพิ่ม row
    try:
        cell = _sheet_sessions.find(user_id)
        if cell:
            r = cell.row
            _sheet_sessions.update(f"A{r}:E{r}", [[_now_str(), user_id, state, json.dumps(data, ensure_ascii=False), str(expire_at)]])
        else:
            _sheet_sessions.append_row([_now_str(), user_id, state, json.dumps(data, ensure_ascii=False), str(expire_at)], value_input_option="RAW")
    except Exception as e:
        app.logger.error(f"save session error: {e}")

def get_session(user_id: str) -> Dict[str, Any]:
    s = _cache_get(user_id)
    if s:
        return s
    # fallback to sheet
    try:
        _ensure_headers()
        s2 = _session_load_from_sheet(user_id)
        if s2:
            _sessions_cache[user_id] = s2
            return s2
    except Exception as e:
        app.logger.error(f"load session error: {e}")

    # default
    s0 = {"state": "IDLE", "data": {}, "expire_at": time.time() + SESSION_TTL}
    _sessions_cache[user_id] = s0
    return s0

def set_session(user_id: str, state: str, data: Dict[str, Any]) -> None:
    expire_at = time.time() + SESSION_TTL
    _cache_set(user_id, state, data, SESSION_TTL)
    try:
        _ensure_headers()
        _session_save_to_sheet(user_id, state, data, expire_at)
    except Exception as e:
        app.logger.error(f"persist session error: {e}")

def clear_session(user_id: str) -> None:
    _sessions_cache.pop(user_id, None)
    # ไม่ลบใน sheet (เก็บเป็น log) แค่ปล่อยหมดอายุ
    set_session(user_id, "IDLE", {})

# ---------- Order ID ----------
def _next_order_id() -> str:
    """สร้าง ORDER_ID แบบ HD0001 โดยดูจากแถวล่าสุด"""
    _load_gspread()
    try:
        last_row = len(_sheet_orders.get_all_values())
        if last_row <= 1:
            return "HD0001"
        last_order_id = _sheet_orders.cell(last_row, 2).value  # col B = ORDER_ID
        if last_order_id and last_order_id.startswith("HD"):
            num = int(last_order_id.replace("HD", ""))
            return f"HD{num+1:04d}"
    except Exception:
        pass
    # fallback
    return f"HD{int(time.time())%10000:04d}"

def _append_order(row: Dict[str, Any]) -> str:
    _ensure_headers()
    order_id = _next_order_id()
    amount = int(row["qty"]) * PRICE_PER_PIECE
    values = [
        _now_str(),
        order_id,
        row["user_id"],
        row["name"],
        row["phone"],
        row["address"],
        row["color"],
        row["size"],
        str(row["qty"]),
        str(amount),
        "NEW",
    ]
    _sheet_orders.append_row(values, value_input_option="RAW")
    return order_id

# ---------- Conversation Flow ----------
def _show_menu(reply_token: str):
    msgs = [
        _msg_text("HARDY SHOP 👖\nพิมพ์ “สั่งซื้อ” เพื่อเริ่มออเดอร์\nหรือพิมพ์ “ราคา” / “สี” / “ไซส์”"),
        _quick_reply("เมนูลัด:", ["สั่งซื้อ", "ราคา", "สี", "ไซส์", "ยกเลิก"]),
    ]
    _line_reply(reply_token, msgs)

def _help_price(reply_token: str):
    _line_reply(reply_token, [_msg_text(f"ราคา HARDY = {PRICE_PER_PIECE} บาท/ตัว\nสี: Dark Coffee, Navy\nไซส์: {', '.join(SIZES)}")])

def _start_order(user_id: str, reply_token: str):
    set_session(user_id, "ASK_COLOR", {"user_id": user_id})
    _line_reply(reply_token, [_quick_reply("เลือกสีครับ:", COLORS)])

def _handle_text(user_id: str, reply_token: str, text: str):
    t = (text or "").strip()

    # global commands
    if t.lower() in ["hi", "hello", "สวัสดี", "หวัดดี", "เริ่ม", "start"]:
        clear_session(user_id)
        return _show_menu(reply_token)

    if t in ["ราคา", "price"]:
        return _help_price(reply_token)

    if t in ["สี", "color"]:
        return _line_reply(reply_token, [_msg_text(f"สีที่มี: {', '.join(COLORS)}")])

    if t in ["ไซส์", "size"]:
        return _line_reply(reply_token, [_msg_text(f"ไซส์ที่มี: {', '.join(SIZES)}")])

    if t in ["ยกเลิก", "cancel", "เลิก"]:
        clear_session(user_id)
        return _line_reply(reply_token, [_msg_text("ยกเลิกเรียบร้อย ✅\nพิมพ์ “สั่งซื้อ” เพื่อเริ่มใหม่ได้เลยครับ")])

    if t in ["สั่งซื้อ", "order", "ซื้อ"]:
        return _start_order(user_id, reply_token)

    # state machine
    s = get_session(user_id)
    state = s["state"]
    data = s["data"] or {}

    # ASK_COLOR
    if state == "ASK_COLOR":
        if t not in COLORS:
            return _line_reply(reply_token, [_quick_reply("สีนี้ยังไม่มีครับ เลือกใหม่:", COLORS)])
        data["color"] = t
        set_session(user_id, "ASK_SIZE", data)
        return _line_reply(reply_token, [_quick_reply("เลือกไซส์ครับ:", SIZES)])

    # ASK_SIZE
    if state == "ASK_SIZE":
        if t not in SIZES:
            return _line_reply(reply_token, [_quick_reply("ไซส์นี้ยังไม่มีครับ เลือกใหม่:", SIZES)])
        data["size"] = t
        set_session(user_id, "ASK_QTY", data)
        return _line_reply(reply_token, [_quick_reply("จำนวนกี่ตัวครับ? (พิมพ์ 1-5)", ["1", "2", "3", "4", "5"])])

    # ASK_QTY
    if state == "ASK_QTY":
        try:
            qty = int(t)
            if qty <= 0 or qty > 20:
                raise ValueError()
        except ValueError:
            return _line_reply(reply_token, [_msg_text("จำนวนไม่ถูกต้องครับ พิมพ์เป็นตัวเลข เช่น 1 / 2 / 3")])
        data["qty"] = qty
        set_session(user_id, "ASK_NAME", data)
        return _line_reply(reply_token, [_msg_text("ขอชื่อ-นามสกุลสำหรับจัดส่งครับ")])

    # ASK_NAME
    if state == "ASK_NAME":
        if len(t) < 2:
            return _line_reply(reply_token, [_msg_text("ชื่อสั้นไปครับ พิมพ์ชื่อ-นามสกุลอีกครั้งนะครับ")])
        data["name"] = t
        set_session(user_id, "ASK_PHONE", data)
        return _line_reply(reply_token, [_msg_text("ขอเบอร์โทรครับ (ตัวเลข 9-10 หลัก)")])

    # ASK_PHONE
    if state == "ASK_PHONE":
        phone = "".join(ch for ch in t if ch.isdigit())
        if len(phone) < 9 or len(phone) > 10:
            return _line_reply(reply_token, [_msg_text("เบอร์โทรไม่ถูกต้องครับ กรุณาพิมพ์ใหม่ (9-10 หลัก)")])
        data["phone"] = phone
        set_session(user_id, "ASK_ADDRESS", data)
        return _line_reply(reply_token, [_msg_text("ขอที่อยู่จัดส่ง (พิมพ์ให้ครบ บ้านเลขที่/หมู่/ถนน/ตำบล/อำเภอ/จังหวัด/รหัสไปรษณีย์)")])

    # ASK_ADDRESS
    if state == "ASK_ADDRESS":
        if len(t) < 10:
            return _line_reply(reply_token, [_msg_text("ที่อยู่สั้นไปครับ พิมพ์ให้ละเอียดอีกนิดนะครับ")])
        data["address"] = t
        set_session(user_id, "CONFIRM", data)

        amount = int(data["qty"]) * PRICE_PER_PIECE
        summary = (
            "สรุปออเดอร์ ✅\n"
            f"- สี: {data['color']}\n"
            f"- ไซส์: {data['size']}\n"
            f"- จำนวน: {data['qty']} ตัว\n"
            f"- ราคารวม: {amount} บาท\n\n"
            f"ชื่อ: {data['name']}\n"
            f"โทร: {data['phone']}\n"
            f"ที่อยู่: {data['address']}\n\n"
            "พิมพ์ “ยืนยัน” เพื่อบันทึกออเดอร์ หรือ “ยกเลิก”"
        )
        return _line_reply(reply_token, [_quick_reply(summary, ["ยืนยัน", "ยกเลิก"])])

    # CONFIRM
    if state == "CONFIRM":
        if t == "ยืนยัน":
            try:
                _load_gspread()
                order_id = _append_order({
                    "user_id": user_id,
                    "name": data["name"],
                    "phone": data["phone"],
                    "address": data["address"],
                    "color": data["color"],
                    "size": data["size"],
                    "qty": data["qty"],
                })
            except Exception as e:
                app.logger.error(f"append order error: {e}")
                return _line_reply(reply_token, [_msg_text("บันทึกออเดอร์ไม่สำเร็จ ❌\nกรุณาลองใหม่อีกครั้ง หรือแจ้งแอดมินครับ")])

            # แจ้งแอดมิน
            if ADMIN_USER_ID:
                amount = int(data["qty"]) * PRICE_PER_PIECE
                admin_msg = (
                    f"🧾 NEW ORDER {order_id}\n"
                    f"{_now_str()}\n"
                    f"USER_ID: {user_id}\n"
                    f"ชื่อ: {data['name']}\n"
                    f"โทร: {data['phone']}\n"
                    f"สี/ไซส์: {data['color']} / {data['size']}\n"
                    f"จำนวน: {data['qty']}  ราคารวม: {amount}\n"
                    f"ที่อยู่: {data['address']}"
                )
                _line_push(ADMIN_USER_ID, [_msg_text(admin_msg)])

            clear_session(user_id)
            return _line_reply(reply_token, [_msg_text(f"รับออเดอร์เรียบร้อย ✅\nเลขออเดอร์: {order_id}\nแอดมินจะติดต่อกลับเพื่อยืนยันการจัดส่งครับ")])

        if t in ["ยกเลิก", "cancel"]:
            clear_session(user_id)
            return _line_reply(reply_token, [_msg_text("ยกเลิกเรียบร้อย ✅\nพิมพ์ “สั่งซื้อ” เพื่อเริ่มใหม่ได้เลยครับ")])

        return _line_reply(reply_token, [_quick_reply("พิมพ์ “ยืนยัน” หรือ “ยกเลิก” ครับ", ["ยืนยัน", "ยกเลิก"])])

    # fallback
    _show_menu(reply_token)

# ---------- Routes ----------
@app.get("/")
def home():
    return "HARDY SHOP ONLINE", 200

@app.get("/healthz")
def healthz():
    return "OK", 200

@app.post("/callback")
def callback():
    body = request.get_data()  # bytes
    signature = request.headers.get("X-Line-Signature", "")

    if not _verify_line_signature(body, signature):
        abort(400)

    payload = request.get_json(silent=True) or {}
    events = payload.get("events", [])

    for ev in events:
        if ev.get("type") != "message":
            continue
        msg = ev.get("message", {})
        if msg.get("type") != "text":
            continue

        reply_token = ev.get("replyToken")
        source = ev.get("source", {})
        user_id = source.get("userId", "")

        if not reply_token or not user_id:
            continue

        text = msg.get("text", "")
        _handle_text(user_id, reply_token, text)

    return "OK", 200


if __name__ == "__main__":
    # Render จะส่ง PORT มาให้
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
