from __future__ import annotations
from typing import Any, Dict, Optional
import time

from core.config import WS_SESSION, SESSION_TTL_SECONDS
from core.utils import now_iso
from services.sheets_service import ensure_worksheet, get_all_records, append_row, find_first_row_index, update_cells

SESSION_HEADERS = ["uid", "state", "data_json", "updated_at", "expires_at"]

import json

def _ensure():
    ensure_worksheet(WS_SESSION, SESSION_HEADERS)

def get_session(uid: str) -> Dict[str, Any]:
    _ensure()
    now = int(time.time())
    rows = get_all_records(WS_SESSION)

    for r in rows:
        if str(r.get("uid")) == uid:
            expires_at = int(r.get("expires_at") or 0)
            if expires_at and now > expires_at:
                # expired -> treat as empty
                return {}
            data_json = r.get("data_json") or "{}"
            try:
                data = json.loads(data_json)
            except Exception:
                data = {}
            return {"uid": uid, "state": r.get("state") or "IDLE", "data": data}
    return {}

def set_session(uid: str, state: str, data: Dict[str, Any]):
    _ensure()
    now = int(time.time())
    expires_at = now + SESSION_TTL_SECONDS

    row_idx = find_first_row_index(WS_SESSION, "uid", uid)
    payload = {
        "uid": uid,
        "state": state,
        "data_json": json.dumps(data, ensure_ascii=False),
        "updated_at": now_iso(),
        "expires_at": str(expires_at),
    }

    if row_idx is None:
        append_row(WS_SESSION, [payload[h] for h in SESSION_HEADERS])
    else:
        update_cells(WS_SESSION, row_idx, payload)

def clear_session(uid: str):
    _ensure()
    row_idx = find_first_row_index(WS_SESSION, "uid", uid)
    if row_idx is None:
        return
    # set as idle and expired
    update_cells(WS_SESSION, row_idx, {
        "state": "IDLE",
        "data_json": "{}",
        "updated_at": now_iso(),
        "expires_at": "0",
    })
