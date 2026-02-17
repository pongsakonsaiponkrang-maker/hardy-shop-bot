# ==========================================================
# HARDY SESSION SERVICE - RENDER FREE SAFE
# Only read one row (no get_all_records)
# ==========================================================

import json
import time
from core.config import WS_SESSION
from services.sheets_service import get_ws

SESSION_TTL = 1800


def get_session(uid: str):
    ws = get_ws(WS_SESSION)
    rows = ws.get_all_values()

    now = int(time.time())

    for i, r in enumerate(rows[1:], start=2):
        if r and r[0] == uid:
            expires = int(r[4]) if len(r) > 4 and r[4] else 0
            if expires < now:
                return None

            return {
                "state": r[1],
                "data": json.loads(r[2] or "{}"),
            }

    return None


def set_session(uid: str, state: str, data: dict):
    ws = get_ws(WS_SESSION)
    rows = ws.get_all_values()

    now = int(time.time())
    expires = now + SESSION_TTL

    for i, r in enumerate(rows[1:], start=2):
        if r and r[0] == uid:
            ws.update(
                f"A{i}",
                [[uid, state, json.dumps(data), now, expires]],
            )
            return

    ws.append_row([uid, state, json.dumps(data), now, expires])


def clear_session(uid: str):
    ws = get_ws(WS_SESSION)
    rows = ws.get_all_values()

    for i, r in enumerate(rows[1:], start=2):
        if r and r[0] == uid:
            ws.update(f"A{i}", [["", "", "", "", ""]])
            return
