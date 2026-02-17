from flask import Flask, request, abort
from core.security import verify_line_signature
from features.order_flow import handle_event
import os

app = Flask(__name__)

# Health check
@app.route("/", methods=["GET"])
def health():
    return {"ok": True, "service": "hardy-shop-bot", "version": "3.2"}

# LINE Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_line_signature(body, signature):
        abort(403)

    payload = request.get_json(silent=True) or {}
    events = payload.get("events", [])

    for ev in events:
        handle_event(ev)

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
