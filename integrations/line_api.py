import requests
from core.config import LINE_CHANNEL_ACCESS_TOKEN

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL  = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"

def _headers():
    return {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

def reply_message(reply_token: str, messages: list):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("WARN: LINE token not set. reply_message skipped.")
        return
    payload = {"replyToken": reply_token, "messages": messages}
    r = requests.post(LINE_REPLY_URL, headers=_headers(), json=payload, timeout=10)
    if r.status_code >= 300:
        print("LINE reply error:", r.status_code, r.text)

def push_message(to_user_id: str, messages: list):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("WARN: LINE token not set. push_message skipped.")
        return
    payload = {"to": to_user_id, "messages": messages}
    r = requests.post(LINE_PUSH_URL, headers=_headers(), json=payload, timeout=10)
    if r.status_code >= 300:
        print("LINE push error:", r.status_code, r.text)

def broadcast_message(messages: list):
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("WARN: LINE token not set. broadcast_message skipped.")
        return
    payload = {"messages": messages}
    r = requests.post(LINE_BROADCAST_URL, headers=_headers(), json=payload, timeout=10)
    if r.status_code >= 300:
        print("LINE broadcast error:", r.status_code, r.text)
