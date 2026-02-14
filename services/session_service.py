# services/session_service.py

import json
import time
from typing import Dict, Any, Optional

from services.sheets_service import get_sessions_sheet
from core.config import SESSION_TTL_SECONDS
from core.utils import safe_int


# --------------------------------------------------
# INTERNAL
# --------------------------------------------------

def _find_row(uid: str) -> Optional[int]:
    """
    Find row number for a user_id in HARDY_SESSION
    Column A = user_id
    """
    sheet = get_sessions_sheet()
    col = sheet.col_values(1)

    # Skip header (row 1)
    for idx, value in enumerate(col[1:], start=2):
        if value.strip() == uid:
            return idx

    return None


# --------------------------------------------------
# PUBLIC API
# --------------------------------------------------

def get_session(uid: str) -> Dict[str, Any]:
    """
    Return:
    {
        "state": str,
        "data": dict,
        "updated_at": int
    }
    """

    sheet = get_sessions_sheet()
    row = _find_row(uid)

    if not row:
        return {"state": "IDLE", "data": {}, "updated_at": 0}

    state = (sheet.cell(row, 2).value or "IDLE").strip()
    data_json = sheet.cell(row, 3).value or "{}"
    updated_at = safe_int(sheet.cell(row, 4).value, 0)

    # TTL check
    if updated_at > 0 and (int(time.time()) - updated_at) > SESSION_TTL_SECONDS:
        clear_session(uid)
        return {"state": "IDLE", "data": {}, "updated_at": 0}

    try:
        data = json.loads(data_json)
    except Exception:
        data = {}

    return {
        "state": state,
        "data": data,
        "updated_at": updated_at
    }


def set_session(uid: str, state: str, data: Dict[str, Any]) -> None:
    """
    Save or update session
    """

    sheet = get_sessions_sheet()
    row = _find_row(uid)

    payload = json.dumps(data, ensure_ascii=False)
    now_ts = int(time.time())

    if row:
        sheet.update(
            f"A{row}:D{row}",
            [[uid, state, payload, str(now_ts)]]
        )
    else:
        sheet.append_row([uid, state, payload, str(now_ts)])


def clear_session(uid: str) -> None:
    """
    Reset session to IDLE
    """

    sheet = get_sessions_sheet()
    row = _find_row(uid)

    if not row:
        return

    now_ts = int(time.time())

    sheet.update(
        f"A{row}:D{row}",
        [[uid, "IDLE", "{}", str(now_ts)]]
    )


def is_in_state(uid: str, state: str) -> bool:
    """
    Helper for checking state quickly
    """
    s = get_session(uid)
    return s["state"] == state