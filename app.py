from flask import Flask, request, abort
from core.security import verify_line_signature
from features.order_flow import handle_event

app = Flask(__name__)

@app.get("/")
def health():
    return {"ok": True, "service": "hardy-shop-bot", "version": "3.1"}

@app.post("/webhook")
def webhook():
    body = request.get_data(as_text=True)
    signature = request.headers.get("X-Line-Signature", "")

    if not verify_line_signature(body, signature):
        abort(403)

    payload = request.get_json(silent=True) or {}
    events = payload.get("events", [])

    for ev in events:
        handle_event(ev)

    return "OK"

if __name__ == "__main__":
    # local run
    app.run(host="0.0.0.0", port=5000, debug=True)
