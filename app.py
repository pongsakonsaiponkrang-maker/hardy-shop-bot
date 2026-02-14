#!/usr/bin/env python3
# ==========================================================
# HARDY LINE SHOP BOT - PRO v2 (Dynamic Price Version)
# - Price per size from HARDY_STOCK sheet
# - Stock deduct + low stock alert
# - Admin notify
# ==========================================================

import os
import json
import time
import hmac
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

import requests
from flask import Flask, request, abort

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

# =========================
# LOAD ENV
# =========================
load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
SHEET_ID = os.getenv("SHEET_ID")
ADMIN_USER_IDS = [
    x.strip() for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip()
]

ORDERS_SHEET_NAME = "HARDY_ORDER"
SESSIONS_SHEET_NAME = "HARDY_SESSION"
STOCK_SHEET_NAME = "HARDY_STOCK"

APP_TZ = timezone(timedelta(hours=7))

# =========================
# INIT
# =========================
app = Flask(__name__)
_gc = None
_sheet_orders = None
_sheet_sessions = None
_sheet_stock = None

# =========================
# UTIL
# =========================
def now_str():
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")

def load_sheets():
    global _gc, _sheet_orders, _sheet_sessions, _sheet_stock

    if _gc:
        return

    info = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))

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

# =========================
# STOCK
# =========================
def get_stock_record(color, size):
    load_sheets()
    records = _sheet_stock.get_all_records()
    for r in records:
        if r["color"] == color and r["size"] == size:
            return r
    return None

def deduct_stock(color, size, qty):
    load_sheets()
    values = _sheet_stock.get_all_values()

    for i in range(2, len(values) + 1):
        row = values[i - 1]
        if row[0] == color and row[1] == size:
            current = int(row[2])
            if current < qty:
                return False, current

            new_stock = current - qty
            _sheet_stock.update_cell(i, 3, new_stock)
            return True, new_stock

    return False, 0

# =========================
# LINE
# =========================
def verify_signature(body, signature):
    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode(),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)

def line_reply(reply_token, messages):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {
        "replyToken": reply_token,
        "messages": messages,
    }

    requests.post(
        "https://api.line.me/v2/bot/message/reply",
        headers=headers,
        json=payload,
    )

def line_push(uid, text):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {
        "to": uid,
        "messages": [{"type": "text", "text": text}],
    }

    requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers=headers,
        json=payload,
    )

# =========================
# FLOW
# =========================
sessions = {}

def handle_text(uid, reply_token, text):
    text = text.strip()

    if text == "สั่งซื้อ":
        sessions[uid] = {"step": "color"}
        return line_reply(reply_token, [{"type": "text", "text": "เลือกสี Dark Coffee / Navy"}])

    if uid not in sessions:
        return line_reply(reply_token, [{"type": "text", "text": "พิมพ์ สั่งซื้อ เพื่อเริ่ม"}])

    data = sessions[uid]

    if data["step"] == "color":
        data["color"] = text
        data["step"] = "size"
        return line_reply(reply_token, [{"type": "text", "text": "เลือกไซส์ XS,S,M,L,XL,XXL"}])

    if data["step"] == "size":
        data["size"] = text
        data["step"] = "qty"
        return line_reply(reply_token, [{"type": "text", "text": "จำนวนกี่ตัว?"}])

    if data["step"] == "qty":
        qty = int(text)
        data["qty"] = qty

        record = get_stock_record(data["color"], data["size"])
        if not record:
            return line_reply(reply_token, [{"type": "text", "text": "ไม่พบสินค้า"}])

        if int(record["stock"]) < qty:
            return line_reply(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ"}])

        price = int(record["price"])
        amount = price * qty

        success, remaining = deduct_stock(
            data["color"], data["size"], qty
        )

        if not success:
            return line_reply(reply_token, [{"type": "text", "text": "สต๊อกเปลี่ยน กรุณาลองใหม่"}])

        order_id = f"HD{int(time.time())}"

        _sheet_orders.append_row([
            now_str(),
            order_id,
            uid,
            data["color"],
            data["size"],
            qty,
            price,
            amount,
        ])

        # แจ้งแอดมิน
        notify = (
            f"🔥 NEW ORDER\n"
            f"ID: {order_id}\n"
            f"{data['color']} {data['size']} x{qty}\n"
            f"ราคาต่อชิ้น {price}\n"
            f"รวม {amount}\n"
            f"เหลือ {remaining}"
        )

        for admin in ADMIN_USER_IDS:
            line_push(admin, notify)

        # เตือน stock ต่ำ
        if remaining <= 3:
            for admin in ADMIN_USER_IDS:
                line_push(admin, f"⚠ STOCK LOW: {data['color']} {data['size']} เหลือ {remaining}")

        sessions.pop(uid)

        return line_reply(reply_token, [{"type": "text", "text": f"รับออเดอร์แล้ว {amount} บาท"}])

# =========================
# ROUTE
# =========================
@app.get("/")
def home():
    return "HARDY PRO BOT RUNNING", 200

@app.post("/callback")
def callback():
    body = request.get_data()
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_signature(body, signature):
        abort(400)

    payload = request.get_json()
    events = payload.get("events", [])

    for ev in events:
        if ev["type"] != "message":
            continue
        if ev["message"]["type"] != "text":
            continue

        uid = ev["source"]["userId"]
        reply_token = ev["replyToken"]
        text = ev["message"]["text"]

        handle_text(uid, reply_token, text)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
