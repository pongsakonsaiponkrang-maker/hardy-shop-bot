# ============================
# HARDY SHOP V3 (REAL SHOP)
# LINE ORDER → GOOGLE SHEET
# ============================

from flask import Flask, request
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# =============================
# CONFIG (ใส่ของคุณตรงนี้)
# =============================

LINE_CHANNEL_ACCESS_TOKEN = "Uqi0zy7Jfr9zjpHJ/JvQWbv2haoMOtiLuKVGQ5A/N0a4eJcYUhv13HiYe7/mCDRBvuBE6c+7QQp+y8nh7S+plzqQoqIql89MPUMB6WIIyzMAbM50THeq8jBFTl2ma16Kj2AzG7zT7bXNsVxYCe3L/gdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "703445d5283a57ec4ffc54b18afbb8e1"

JSON_KEY = "hardy_bot_.json"
SHEET_NAME = "HARDY_ORDER"

# =============================
# GOOGLE SHEET
# =============================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_file(
    JSON_KEY,
    scopes=SCOPES
)

gc = gspread.authorize(creds)
sheet = gc.open(SHEET_NAME).sheet1

# =============================
# LINE BOT
# =============================

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# เก็บ state ลูกค้า
user_state = {}

# =============================
# CALLBACK
# =============================

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    handler.handle(body, signature)

    return "OK", 200


# =============================
# MESSAGE HANDLER
# =============================

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_state:
        user_state[user_id] = {}

    state = user_state[user_id]

    # ====================
    # START
    # ====================

    if text.lower() in ["hi", "hello", "สวัสดี"]:

        msg = (
            "สวัสดีครับ 🙂\n"
            "HARDY กางเกง Workwear\n\n"
            "ตอนนี้มี 2 สี:\n"
            "• Dark Coffee ☕\n"
            "• Navy 🔵\n\n"
            "พิมพ์ 'สั่งซื้อ' เพื่อเริ่มครับ"
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg)
        )
        return

    # ====================
    # ORDER FLOW
    # ====================

    if text == "สั่งซื้อ":
        state["step"] = "name"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="กรุณาพิมพ์ชื่อผู้สั่งซื้อ")
        )
        return

    if state.get("step") == "name":
        state["name"] = text
        state["step"] = "phone"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="กรุณาพิมพ์เบอร์โทร")
        )
        return

    if state.get("step") == "phone":
        state["phone"] = text
        state["step"] = "address"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="กรุณาพิมพ์ที่อยู่จัดส่ง")
        )
        return

    if state.get("step") == "address":
        state["address"] = text
        state["step"] = "color"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="เลือกสี: Dark Coffee / Navy")
        )
        return

    if state.get("step") == "color":
        state["color"] = text
        state["step"] = "size"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="เลือกไซส์: S / M / L / XL")
        )
        return

    if state.get("step") == "size":
        state["size"] = text

        # ====================
        # SAVE TO SHEET
        # ====================

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet.append_row([
            now,
            user_id,
            state["name"],
            state["phone"],
            state["address"],
            state["color"],
            state["size"],
            "NEW"
        ])

        # reset
        user_state[user_id] = {}

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="✅ รับออเดอร์แล้วครับ ขอบคุณที่สั่ง HARDY 🙏")
        )
        return

    # ====================
    # DEFAULT
    # ====================

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="พิมพ์ 'สั่งซื้อ' เพื่อเริ่มสั่งกางเกงครับ 🙂")
    )


# =============================
# RUN
# =============================

if __name__ == "__main__":
    print("HARDY SHOP V3 STARTED...")
    app.run(host="0.0.0.0", port=5000)
