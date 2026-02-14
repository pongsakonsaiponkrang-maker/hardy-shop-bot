# core/security.py

import hmac
import base64
import hashlib
from core.config import LINE_CHANNEL_SECRET


def verify_signature(body: bytes, signature: str) -> bool:
    """
    Verify LINE webhook signature
    """
    if not LINE_CHANNEL_SECRET:
        return False

    mac = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()

    expected = base64.b64encode(mac).decode("utf-8")

    return hmac.compare_digest(expected, signature)