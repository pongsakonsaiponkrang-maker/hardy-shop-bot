# ==========================================================
# HARDY SESSION SERVICE - CLEAN VERSION
# ==========================================================

import json
import time
from core.config import WS_SESSION
from services.sheets_service import (
    get_all_records,
    append_row,
    update_row,
    find_row_by_value,
)

SESSION_TTL = 1800  # 30 min


def get_session(uid: str):
    rows = get_all_records(WS_SESSION)
    now = int(time.time())

    for r in rows:
        if r.get("uid") == uid:
            if int(r.get("expires_at") or 0) < now:
                return None

            return {
                "state": r.get("state"),
                "data": json.loads(r.get("data_json") or "{}"),
            }

    return None


def set_session(uid: str, state: str, data: dict):
    now = int(time.time())
    expires = now + SESSION_TTL

    row_index = find_row_by_value(WS_SESSION, "uid", uid)

    row_data = [
        uid,
        state,
        json.dumps(data),
        now,
        expires,
    ]

    if row_index:
        update_row(WS_SESSION, row_index, row_data)
    else:
        append_row(WS_SESSION, row_data)


def clear_session(uid: str):
    row_index = find_row_by_value(WS_SESSION, "uid", uid)
    if row_index:
        update_row(WS_SESSION, row_index, ["", "", "", "", ""])
