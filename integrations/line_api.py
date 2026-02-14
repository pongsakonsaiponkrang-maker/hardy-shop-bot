# integrations/line_api.py

import requests
from typing import List, Dict, Tuple, Optional

from core.config import LINE_CHANNEL_ACCESS_TOKEN

LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
    }


# ---------------- API ----------------

def reply_message(reply_token: str, messages: List[Dict]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    payload = {"replyToken": reply_token, "messages": messages}
    requests.post(LINE_REPLY_URL, headers=_headers(), json=payload, timeout=15)


def push_message(user_id: str, messages: List[Dict]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    payload = {"to": user_id, "messages": messages}
    requests.post(LINE_PUSH_URL, headers=_headers(), json=payload, timeout=15)


# ---------------- Basic Messages ----------------

def text_message(text: str) -> Dict:
    return {"type": "text", "text": text}


def quick_reply_message(text: str, items: List[Tuple[str, str]]) -> Dict:
    """
    items: [(label, send_text)]
    """
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {"type": "message", "label": label, "text": send_text},
                }
                for (label, send_text) in items
            ]
        }
    }


# ---------------- Template: Buttons (max 4 actions) ----------------

def buttons_message(title: str, text: str, actions: List[Tuple[str, str]], alt_text: Optional[str] = None) -> Dict:
    """
    actions: [(label, send_text)] <= 4
    """
    return {
        "type": "template",
        "altText": alt_text or title,
        "template": {
            "type": "buttons",
            "title": title[:40],
            "text": text[:160],
            "actions": [
                {"type": "message", "label": label[:20], "text": send_text}
                for (label, send_text) in actions[:4]
            ],
        },
    }


# ---------------- Template: Carousel (each column max 3 actions) ----------------

def carousel_message(alt_text: str, columns: List[Dict]) -> Dict:
    """
    columns = [
      {
        "title": "...",
        "text": "...",
        "actions": [(label, send_text), ...]  # <= 3
      },
      ...
    ]
    """
    return {
        "type": "template",
        "altText": alt_text[:400],
        "template": {
            "type": "carousel",
            "columns": [
                {
                    "title": col.get("title", "")[:40],
                    "text": col.get("text", "")[:60],
                    "actions": [
                        {"type": "message", "label": a[0][:20], "text": a[1]}
                        for a in col.get("actions", [])[:3]
                    ],
                }
                for col in columns[:10]  # LINE จำกัดจำนวนคอลัมน์
            ],
        },
    }


# ---------------- Flex Message (Brand UI) ----------------

def flex_message(alt_text: str, contents: Dict) -> Dict:
    return {
        "type": "flex",
        "altText": alt_text[:400],
        "contents": contents,
    }


def flex_product_card(brand: str, color: str, size: str, price: int, stock: int) -> Dict:
    """
    Flex bubble สวย ๆ แสดงสี/ไซส์/ราคา/สต๊อก
    """
    return flex_message(
        f"{brand} {color} {size}",
        {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": brand, "weight": "bold", "size": "xl"},
                    {"type": "text", "text": "Utility Chino", "size": "md", "color": "#666666"},
                    {"type": "separator"},
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {"type": "text", "text": f"Color: {color}", "size": "md"},
                            {"type": "text", "text": f"Size: {size}", "size": "md"},
                            {"type": "text", "text": f"Price: {price:,} THB / pcs", "size": "md", "weight": "bold"},
                            {"type": "text", "text": f"In stock: {stock}", "size": "sm", "color": "#666666"},
                        ],
                    },
                ],
            },
        },
    )


def flex_order_summary(order_id: str, data: Dict, total: int) -> Dict:
    return flex_message(
        f"ORDER {order_id}",
        {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {"type": "text", "text": "✅ ORDER CONFIRMED", "weight": "bold", "size": "xl"},
                    {"type": "text", "text": f"ORDER ID: {order_id}", "size": "sm", "color": "#666666"},
                    {"type": "separator"},
                    {"type": "text", "text": f"{data['color']} / {data['size']} x {data['qty']}", "size": "md"},
                    {"type": "text", "text": f"Price: {int(data['price']):,} THB", "size": "sm", "color": "#666666"},
                    {"type": "text", "text": f"Total: {total:,} THB", "size": "lg", "weight": "bold"},
                    {"type": "separator"},
                    {"type": "text", "text": "แอดมินจะติดต่อกลับเพื่อสรุปชำระเงิน/จัดส่ง", "size": "sm", "wrap": True},
                ],
            },
        },
    )