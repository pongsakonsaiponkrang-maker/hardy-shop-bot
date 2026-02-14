#!/usr/bin/env python3
# ==========================================================
# HARDY LINE SHOP BOT - HARDY PRO v3
# - Dynamic price per size
# - Show price + stock before confirm
# - Low stock alert
# - Admin tools
# - Production ready
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

# ---------------- ENV ----------------
load_dotenv()
APP_TZ = timezone(timedelta(hours=7))

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()
SHEET_ID = os.getenv("SHEET_ID", "").strip()

ORDERS_SHEET_NAME = "HARDY_ORDER"
SESSIONS_SHEET_NAME = "HARDY_SESSION"
STOCK_SHEET_NAME = "HARDY_STOCK"

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
ADMIN_USER_IDS = [x.strip() for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()]
LOW_STOCK_ALERT = int(os.getenv("LOW_STOCK_ALERT", "3"))

COLORS = ["Dark Coffee", "Navy"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

SESSION_TTL_SECONDS = 1800

app = Flask(__name__)

_gc = None
_sheet_orders = None
_sheet_sessions = None
_sheet_stock = None


# ---------------- UTILS ----------------
def now_str():
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")

def safe_int(v, default=0):
    try:
        return int(str(v))
    except:
        return default

def is_admin(uid):
    return uid in ADMIN_USER_IDS


# ---------------- SHEETS ----------------
def load_sheets():
    global _gc, _sheet_orders, _sheet_sessions, _sheet_stock
    if _gc:
        return

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


# ---------------- STOCK ----------------
def stock_record(color, size):
    load_sheets()
    for r in _sheet_stock.get_all_records():
        if r["color"] == color and r["size"] == size:
            return r
    return None

def stock_get(color, size):
    r = stock_record(color, size)
    return safe_int(r["stock"]) if r else 0

def price_get(color, size):
    r = stock_record(color, size)
    return safe_int(r["price"]) if r else 0

def stock_deduct(color, size, qty):
    load_sheets()
    values = _sheet_stock.get_all_values()
    header = values[0]
    col_stock = header.index("stock") + 1

    for i in range(2, len(values) + 1):
        row = values[i-1]
        if row[0] == color and row[1] == size:
            current = safe_int(row[col_stock-1])
            if current < qty:
                return False, current
            new_stock = current - qty
            _sheet_stock.update_cell(i, col_stock, new_stock)
            return True, new_stock
    return False, 0


# ---------------- LINE ----------------
def verify_signature(body, signature):
    mac = hmac.new(LINE_CHANNEL_SECRET.encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)

def line_reply(token, messages):
    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"replyToken": token, "messages": messages},
    )

def line_push(uid, text):
    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"to": uid, "messages": [{"type": "text", "text": text}]},
    )

def msg(text):
    return {"type": "text", "text": text}


# ---------------- FLOW ----------------
sessions = {}

def handle(uid, reply_token, text):
    text = text.strip()

    if text == "เมนู":
        return line_reply(reply_token, [msg("พิมพ์ สั่งซื้อ เพื่อเริ่ม")])

    if text == "สั่งซื้อ":
        sessions[uid] = {"step": "color"}
        return line_reply(reply_token, [msg("เลือกสี: Dark Coffee / Navy")])

    if uid not in sessions:
        return line_reply(reply_token, [msg("พิมพ์ สั่งซื้อ เพื่อเริ่ม")])

    data = sessions[uid]

    if data["step"] == "color":
        data["color"] = text
        data["step"] = "size"
        return line_reply(reply_token, [msg("เลือกไซส์ XS,S,M,L,XL,XXL")])

    if data["step"] == "size":
        data["size"] = text
        stock = stock_get(data["color"], data["size"])
        price = price_get(data["color"], data["size"])

        if stock <= 0:
            return line_reply(reply_token, [msg("สต๊อกหมด ❌ เลือกใหม่")])

        data["price"] = price
        data["step"] = "qty"
        return line_reply(reply_token, [
            msg(f"ไซส์ {text}\nราคา {price} บาท\nคงเหลือ {stock}\n\nจำนวนกี่ตัว?")
        ])

    if data["step"] == "qty":
        qty = safe_int(text)
        stock = stock_get(data["color"], data["size"])

        if qty > stock:
            return line_reply(reply_token, [msg(f"สต๊อกเหลือ {stock}")])

        ok, remaining = stock_deduct(data["color"], data["size"], qty)
        if not ok:
            return line_reply(reply_token, [msg("สต๊อกเปลี่ยน กรุณาใหม่")])

        amount = qty * data["price"]

        order_id = f"HD{int(time.time())}"

        _sheet_orders.append_row([
            now_str(),
            order_id,
            uid,
            data["color"],
            data["size"],
            qty,
            data["price"],
            amount,
            "NEW",
        ])

        for admin in ADMIN_USER_IDS:
            line_push(admin, f"NEW ORDER {order_id}\n{data['color']} {data['size']} x{qty}\nรวม {amount}\nเหลือ {remaining}")

            if remaining <= LOW_STOCK_ALERT:
                line_push(admin, f"⚠ STOCK LOW {data['color']} {data['size']} เหลือ {remaining}")

        sessions.pop(uid)

        return line_reply(reply_token, [msg(f"รับออเดอร์แล้ว {amount} บาท")])

@app.get("/")
def home():
    return "HARDY PRO BOT v3 RUNNING", 200

@app.post("/callback")
def callback():
    body = request.get_data()
    sig = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, sig):
        abort(400)

    payload = request.get_json()
    for ev in payload.get("events", []):
        if ev["type"] == "message" and ev["message"]["type"] == "text":
            handle(ev["source"]["userId"], ev["replyToken"], ev["message"]["text"])
    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
