# ==========================================================
# HARDY LINE SHOP BOT (Clean Production Version)
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

# ---------- LOAD ENV ----------
load_dotenv()

APP_TZ = timezone(timedelta(hours=7))

# ---------- ENV ----------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

SHEET_ID = os.getenv("SHEET_ID", "")
ORDERS_SHEET_NAME = os.getenv("ORDERS_SHEET_NAME", "HARDY_ORDER")
SESSIONS_SHEET_NAME = os.getenv("SESSIONS_SHEET_NAME", "HARDY_SESSION")

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")

PRICE_PER_PIECE = int(os.getenv("PRICE_PER_PIECE", "1290"))

COLORS = ["Dark Coffee", "Navy"]
SIZES = ["XS", "S", "M", "L", "XL", "XXL"]

# ---------- APP ----------
app = Flask(__name__)

_gc = None
_sheet_orders = None


# ---------- BASIC ----------
def now_str():
    return datetime.now(APP_TZ).strftime("%Y-%m-%d %H:%M:%S")


# ---------- GOOGLE SHEET ----------
def load_sheet():
    global _gc, _sheet_orders

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


def append_order(data):
    load_sheet()

    order_id = f"HD{int(time.time())}"

    amount = data["qty"] * PRICE_PER_PIECE

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
            data["qty"],
            amount,
            "NEW",
        ]
    )

    return order_id


# ---------- LINE ----------
def verify_signature(body, signature):
    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode(),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(mac).decode()
    return hmac.compare_digest(expected, signature)


def line_reply(reply_token, messages):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }

    payload = {
        "replyToken": reply_token,
        "messages": messages,
    }

    requests.post(url, headers=headers, json=payload)


def msg(text):
    return {"type": "text", "text": text}


# ---------- MEMORY SESSION ----------
sessions: Dict[str, Dict[str, Any]] = {}


def get_session(uid):
    return sessions.get(uid, {"state": "IDLE", "data": {}})


def set_session(uid, state, data):
    sessions[uid] = {"state": state, "data": data}


# ---------- FLOW ----------
def handle_text(uid, reply_token, text):

    s = get_session(uid)
    state = s["state"]
    data = s["data"]

    # START
    if text in ["สั่งซื้อ", "order"]:
        set_session(uid, "ASK_COLOR", {"user_id": uid})
        return line_reply(reply_token, [msg("เลือกสี: Dark Coffee / Navy")])

    # COLOR
    if state == "ASK_COLOR":
        if text not in COLORS:
            return line_reply(reply_token, [msg("สีไม่ถูกต้อง")])

        data["color"] = text
        set_session(uid, "ASK_SIZE", data)
        return line_reply(reply_token, [msg("เลือกไซส์ XS,S,M,L,XL,XXL")])

    # SIZE
    if state == "ASK_SIZE":
        if text not in SIZES:
            return line_reply(reply_token, [msg("ไซส์ไม่ถูกต้อง")])

        data["size"] = text
        set_session(uid, "ASK_QTY", data)
        return line_reply(reply_token, [msg("จำนวนกี่ตัว?")])

    # QTY
    if state == "ASK_QTY":
        try:
            qty = int(text)
        except:
            return line_reply(reply_token, [msg("ใส่จำนวนเป็นตัวเลข")])

        data["qty"] = qty
        set_session(uid, "ASK_NAME", data)
        return line_reply(reply_token, [msg("ชื่อ-นามสกุล?")])

    # NAME
    if state == "ASK_NAME":
        data["name"] = text
        set_session(uid, "ASK_PHONE", data)
        return line_reply(reply_token, [msg("เบอร์โทร?")])

    # PHONE
    if state == "ASK_PHONE":
        data["phone"] = text
        set_session(uid, "ASK_ADDRESS", data)
        return line_reply(reply_token, [msg("ที่อยู่จัดส่ง?")])

    # ADDRESS
    if state == "ASK_ADDRESS":
        data["address"] = text

        order_id = append_order(data)

        sessions.pop(uid, None)

        return line_reply(
            reply_token,
            [msg(f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}")]
        )

    # DEFAULT
    line_reply(reply_token, [msg("พิมพ์ 'สั่งซื้อ' เพื่อเริ่ม")])

# ---------- ROUTES ----------
@app.get("/")
def home():
    return "HARDY BOT RUNNING", 200


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
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
