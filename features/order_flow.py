# ==========================================================
# HARDY ORDER FLOW - V3.1 PRODUCTION SAFE
# Strict State / Anti-Skip / Anti-Double Confirm / Idempotent
# parse_payload() / quickReply limit + fallback
# ==========================================================

from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any

from integrations.line_api import reply_message
from services.stock_service import (
    get_available_colors,
    get_available_sizes,
    get_stock,
    get_price,
    deduct_stock,
)
from services.session_service import (
    get_session,
    set_session,
    clear_session,
)
from core.config import QUICK_REPLY_LIMIT
from core.utils import shorten_label, safe_int, gen_token

# ----------------------------------------------------------
# Payload Helper
# ----------------------------------------------------------

def parse_payload(text: str) -> Tuple[str, List[str]]:
    """
    Returns (cmd, parts)
    Example:
      "BOT:COLOR:Navy" -> ("BOT", ["COLOR","Navy"])
      "BOT:QTY:Navy:M:2" -> ("BOT", ["QTY","Navy","M","2"])
    If not payload, cmd="".
    """
    t = (text or "").strip()
    if not t.startswith("BOT:"):
        return "", []
    parts = t.split(":")
    if len(parts) < 2:
        return "", []
    cmd = parts[0]  # "BOT"
    return cmd, parts[1:]


# ----------------------------------------------------------
# Quick Reply builder with limit + fallback
# ----------------------------------------------------------

def build_quick_or_fallback(text: str, buttons: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    If buttons <= QUICK_REPLY_LIMIT: return 1 quick reply message
    Else: return text list + quick with first QUICK_REPLY_LIMIT buttons
    """
    buttons = buttons or []
    if len(buttons) <= QUICK_REPLY_LIMIT:
        return [quick(text, buttons)]

    # fallback list (user can still tap from first 13 quick buttons)
    lines = [text, ""]
    # show list for all items
    for i, (label, payload) in enumerate(buttons, start=1):
        lines.append(f"{i}. {label}")

    fallback_text = "\n".join(lines).strip()
    limited = buttons[:QUICK_REPLY_LIMIT]
    return [
        {"type": "text", "text": fallback_text},
        quick("เลือกจากปุ่มด้านล่าง (แสดงบางส่วน):", limited),
    ]


def quick(text: str, buttons: List[Tuple[str, str]]) -> Dict[str, Any]:
    buttons = (buttons or [])[:QUICK_REPLY_LIMIT]
    return {
        "type": "text",
        "text": text,
        "quickReply": {
            "items": [
                {
                    "type": "action",
                    "action": {
                        "type": "message",
                        "label": shorten_label(label, 20),
                        "text": payload,
                    },
                }
                for label, payload in buttons
            ]
        },
    }


# ----------------------------------------------------------
# Menu
# ----------------------------------------------------------

def send_menu(reply_token: str):
    msgs = build_quick_or_fallback(
        "👖 HARDY\nเลือกเมนู:",
        [
            ("🛒 สั่งซื้อ", "BOT:ORDER"),
            ("🎨 ดูสี", "BOT:COLORS"),
            ("💬 คุยกับแอดมิน", "BOT:ADMIN"),
        ],
    )
    reply_message(reply_token, msgs)


# ----------------------------------------------------------
# State guard
# ----------------------------------------------------------

def require_state(uid: str, reply_token: str, expected_state: str) -> bool:
    session = get_session(uid) or {}
    if session.get("state") != expected_state:
        send_menu(reply_token)
        return False
    return True


# ----------------------------------------------------------
# Main flow
# ----------------------------------------------------------

def handle(uid: str, reply_token: str, text: str):
    session = get_session(uid) or {}
    state = session.get("state", "IDLE")
    data = session.get("data", {}) or {}

    plain = (text or "").strip()

    # --- Global shortcuts ---
    if plain.lower() in ["เมนู", "menu", "hi", "hello", "start"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    cmd, parts = parse_payload(plain)

    # --- MENU: colors ---
    if cmd == "BOT" and parts[:1] == ["COLORS"]:
        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return
        reply_message(reply_token, [{"type": "text", "text": "🎨 สีที่มี: " + ", ".join(colors)}])
        send_menu(reply_token)
        return

    # --- START ORDER ---
    if cmd == "BOT" and parts[:1] == ["ORDER"]:
        clear_session(uid)

        colors = get_available_colors()
        if not colors:
            reply_message(reply_token, [{"type": "text", "text": "สินค้าหมด ❌"}])
            return

        buttons = [(c, f"BOT:COLOR:{c}") for c in colors]
        msgs = build_quick_or_fallback("เลือกสี:", buttons)
        reply_message(reply_token, msgs)

        set_session(uid, "WAIT_COLOR", {})
        return

    # --- COLOR ---
    if cmd == "BOT" and parts[:1] == ["COLOR"]:
        if not require_state(uid, reply_token, "WAIT_COLOR"):
            return
        if len(parts) != 2:
            send_menu(reply_token)
            return

        color = parts[1].strip()
        sizes = get_available_sizes(color)
        if not sizes:
            reply_message(reply_token, [{"type": "text", "text": "สีนี้หมด ❌"}])
            return

        buttons = []
        for s in sizes:
            price = get_price(color, s)
            stock = get_stock(color, s)
            buttons.append((f"{s} | {price}฿ | {stock}", f"BOT:SIZE:{color}:{s}"))

        msgs = build_quick_or_fallback(f"สี {color}\nเลือกไซส์:", buttons)
        reply_message(reply_token, msgs)

        set_session(uid, "WAIT_SIZE", {"color": color})
        return

    # --- SIZE ---
    if cmd == "BOT" and parts[:1] == ["SIZE"]:
        if not require_state(uid, reply_token, "WAIT_SIZE"):
            return
        if len(parts) != 3:
            send_menu(reply_token)
            return

        color, size = parts[1].strip(), parts[2].strip()

        # anti-skip: ensure same color
        if data.get("color") != color:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        price = get_price(color, size)
        if stock <= 0:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกหมด ❌"}])
            return

        max_btn = min(stock, 5)
        buttons = [(str(n), f"BOT:QTY:{color}:{size}:{n}") for n in range(1, max_btn + 1)]
        msgs = build_quick_or_fallback(
            f"{color} / {size}\nราคา {price} บาท\nเลือกจำนวน:",
            buttons,
        )
        reply_message(reply_token, msgs)

        set_session(uid, "WAIT_QTY", {"color": color, "size": size})
        return

    # --- QTY ---
    if cmd == "BOT" and parts[:1] == ["QTY"]:
        if not require_state(uid, reply_token, "WAIT_QTY"):
            return
        if len(parts) != 4:
            send_menu(reply_token)
            return

        color, size, qty_str = parts[1].strip(), parts[2].strip(), parts[3].strip()

        if data.get("color") != color or data.get("size") != size:
            send_menu(reply_token)
            return

        qty = safe_int(qty_str, 0)
        if qty <= 0:
            send_menu(reply_token)
            return

        stock = get_stock(color, size)
        if qty > stock:
            reply_message(reply_token, [{"type": "text", "text": "สต๊อกไม่พอ ❌"}])
            return

        price = get_price(color, size)
        total = qty * price

        # Idempotency token for this confirm step
        confirm_token = gen_token()

        set_session(
            uid,
            "WAIT_CONFIRM",
            {
                "color": color,
                "size": size,
                "qty": qty,
                "price": price,
                "total": total,
                "confirm_token": confirm_token,
                "confirm_lock": False,
            },
        )

        reply_message(
            reply_token,
            build_quick_or_fallback(
                f"🧾 สรุป\n{color} / {size}\n{qty} ตัว\nรวม {total} บาท",
                [
                    ("✅ ยืนยัน", "BOT:CONFIRM"),
                    ("❌ ยกเลิก", "BOT:CANCEL"),
                ],
            ),
        )
        return

    # --- CONFIRM (Idempotent + Lock) ---
    if cmd == "BOT" and parts[:1] == ["CONFIRM"]:
        if not require_state(uid, reply_token, "WAIT_CONFIRM"):
            return

        # reload latest session to avoid stale `data`
        session = get_session(uid) or {}
        data = session.get("data", {}) or {}

        # hard guard
        needed = ["color", "size", "qty", "price", "total", "confirm_token"]
        if any(k not in data for k in needed):
            send_menu(reply_token)
            return

        # 1) If locked -> tell user it's processing
        if data.get("confirm_lock") is True:
            reply_message(reply_token, [{"type": "text", "text": "ระบบกำลังดำเนินการ ✅"}])
            return

        # 2) Lock immediately (anti double-tap / LINE retry)
        data["confirm_lock"] = True
        set_session(uid, "WAIT_CONFIRM", data)

        # 3) Idempotent check in order_service
        from services.order_service import find_order_by_confirm_token, create_order
        existed_order_id = find_order_by_confirm_token(data["confirm_token"])
        if existed_order_id:
            clear_session(uid)
            reply_message(
                reply_token,
                [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {existed_order_id}"}],
            )
            return

        # 4) Deduct stock (may fail if stock changed)
        ok, remain = deduct_stock(data["color"], data["size"], int(data["qty"]))
        if not ok:
            clear_session(uid)
            reply_message(
                reply_token,
                build_quick_or_fallback(
                    "สต๊อกไม่พอ ❌ (อาจมีคนสั่งตัดหน้าคุณ)\nกดสั่งซื้อใหม่ได้เลย",
                    [("🛒 สั่งซื้อ", "BOT:ORDER"), ("เมนู", "เมนู")],
                ),
            )
            return

        # 5) Create order (guaranteed idempotent by token)
        order_id = create_order(uid, data)

        # 6) Notify admin
        from services.admin_service import notify_admin_new_order
        notify_admin_new_order(order_id, data, remain)

        clear_session(uid)
        reply_message(reply_token, [{"type": "text", "text": f"รับออเดอร์แล้ว ✅\nORDER ID: {order_id}"}])
        return

    # --- CANCEL ---
    if cmd == "BOT" and parts[:1] == ["CANCEL"]:
        clear_session(uid)
        send_menu(reply_token)
        return

    # --- ADMIN CHAT ---
    if cmd == "BOT" and parts[:1] == ["ADMIN"]:
        set_session(uid, "ADMIN_CHAT", {})
        reply_message(reply_token, [{"type": "text", "text": "พิมพ์ข้อความส่งหาแอดมินได้เลย"}])
        return

    if state == "ADMIN_CHAT":
        from services.admin_service import forward_to_admin
        forward_to_admin(uid, plain)
        reply_message(reply_token, [{"type": "text", "text": "ส่งถึงแอดมินแล้ว ✅"}])
        return

    # --- DEFAULT ---
    send_menu(reply_token)


# ----------------------------------------------------------
# Entry
# ----------------------------------------------------------

def handle_event(event: dict):
    try:
        if event.get("type") != "message":
            return

        message = event.get("message", {})
        if message.get("type") != "text":
            return

        uid = event["source"]["userId"]
        reply_token = event["replyToken"]
        text = (message.get("text") or "").strip()

        handle(uid, reply_token, text)

    except Exception as e:
        print("ORDER FLOW ERROR:", e)
