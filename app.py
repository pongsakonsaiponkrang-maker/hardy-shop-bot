#!/usr/bin/env python3
# ==========================================================
# HARDY LINE SHOP BOT - app.py (Entry Point)
# - Flask webhook receiver
# - Signature verification
# - Dispatch events to features/order_flow.py
# ==========================================================

from __future__ import annotations

import json
import traceback
from flask import Flask, request, abort

from core.security import verify_signature
from features.order_flow import handle_event

app = Flask(__name__)


@app.get("/")
def home():
    # Simple health check for Render / uptime monitoring
    return "HARDY PRO BOT RUNNING", 200


@app.post("/callback")
def callback():
    # 1) Get raw body for signature verification
    body: bytes = request.get_data() or b""
    signature: str = request.headers.get("X-Line-Signature", "") or ""

    if not verify_signature(body, signature):
        abort(400)

    # 2) Parse JSON payload safely
    payload = request.get_json(silent=True) or {}
    events = payload.get("events", []) or []

    # 3) Handle events one by one (never crash webhook)
    for ev in events:
        try:
            handle_event(ev)
        except Exception:
            # IMPORTANT: do not crash webhook; log to stdout for Render Logs
            print("ERROR: handle_event failed")
            print("EVENT:", json.dumps(ev, ensure_ascii=False))
            print(traceback.format_exc())

    return "OK", 200


if __name__ == "__main__":
    # For local run (Render uses Start Command)
    import os

    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)