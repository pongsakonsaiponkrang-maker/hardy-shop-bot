import base64
import hmac
import hashlib
from core.config import LINE_CHANNEL_SECRET

def verify_line_signature(body: str, signature: str) -> bool:
    if not LINE_CHANNEL_SECRET:
        # If not configured, fail safe
        return False

    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(mac).decode("utf-8")

    # constant-time compare
    return hmac.compare_digest(expected, signature or "")
