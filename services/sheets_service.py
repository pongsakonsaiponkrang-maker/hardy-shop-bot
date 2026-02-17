from __future__ import annotations
import json
import threading
from typing import Any, Dict, List, Optional, Tuple

import gspread
from google.oauth2.service_account import Credentials

from core.config import (
    SHEET_ID,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SERVICE_ACCOUNT_FILE,
)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_lock = threading.Lock()
_client = None
_sheet = None

# --- In-memory fallback (for local test if Sheets not configured) ---
_MEMORY: Dict[str, List[List[Any]]] = {}

def _get_creds():
    if GOOGLE_SERVICE_ACCOUNT_JSON:
        info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        return Credentials.from_service_account_info(info, scopes=_SCOPES)
    if GOOGLE_SERVICE_ACCOUNT_FILE:
        return Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=_SCOPES)
    return None

def _init():
    global _client, _sheet
    if _sheet is not None:
        return

    creds = _get_creds()
    if not SHEET_ID or creds is None:
        _sheet = None
        return

    _client = gspread.authorize(creds)
    _sheet = _client.open_by_key(SHEET_ID)

def is_sheets_ready() -> bool:
    with _lock:
        _init()
        return _sheet is not None

def ensure_worksheet(ws_name: str, headers: List[str]):
    with _lock:
        _init()
        if _sheet is None:
            # fallback memory
            if ws_name not in _MEMORY:
                _MEMORY[ws_name] = [headers]
            return

        try:
            ws = _sheet.worksheet(ws_name)
        except Exception:
            ws = _sheet.add_worksheet(title=ws_name, rows=1000, cols=max(10, len(headers)))

        # ensure header row
        values = ws.row_values(1)
        if not values:
            ws.append_row(headers)
        else:
            # If headers mismatch, we won't override automatically.
            pass

def get_all_records(ws_name: str) -> List[Dict[str, Any]]:
    with _lock:
        _init()
        if _sheet is None:
            rows = _MEMORY.get(ws_name, [])
            if len(rows) < 2:
                return []
            headers = rows[0]
            out = []
            for r in rows[1:]:
                row = r + [""] * (len(headers) - len(r))
                out.append({headers[i]: row[i] for i in range(len(headers))})
            return out

        ws = _sheet.worksheet(ws_name)
        return ws.get_all_records()

def append_row(ws_name: str, row: List[Any]):
    with _lock:
        _init()
        if _sheet is None:
            _MEMORY.setdefault(ws_name, [[]])
            _MEMORY[ws_name].append(row)
            return

        ws = _sheet.worksheet(ws_name)
        ws.append_row(row, value_input_option="USER_ENTERED")

def find_first_row_index(ws_name: str, col_name: str, value: str) -> Optional[int]:
    """
    Return 2-based row index in sheet (because header is row 1).
    """
    value = str(value)
    with _lock:
        _init()
        if _sheet is None:
            rows = _MEMORY.get(ws_name, [])
            if not rows:
                return None
            headers = rows[0]
            if col_name not in headers:
                return None
            idx = headers.index(col_name)
            for i, r in enumerate(rows[1:], start=2):
                if idx < len(r) and str(r[idx]) == value:
                    return i
            return None

        ws = _sheet.worksheet(ws_name)
        headers = ws.row_values(1)
        if col_name not in headers:
            return None
        col_idx = headers.index(col_name) + 1
        col_values = ws.col_values(col_idx)
        for i, v in enumerate(col_values[1:], start=2):
            if str(v) == value:
                return i
        return None

def update_cells(ws_name: str, row_index: int, updates: Dict[str, Any]):
    """
    Update columns in a specific row (row_index is 2-based).
    """
    with _lock:
        _init()
        if _sheet is None:
            rows = _MEMORY.get(ws_name, [])
            if not rows:
                return
            headers = rows[0]
            rpos = row_index - 1
            while len(rows) <= rpos:
                rows.append([""] * len(headers))
            row = rows[rpos]
            if len(row) < len(headers):
                row += [""] * (len(headers) - len(row))
            for k, val in updates.items():
                if k in headers:
                    row[headers.index(k)] = val
            rows[rpos] = row
            _MEMORY[ws_name] = rows
            return

        ws = _sheet.worksheet(ws_name)
        headers = ws.row_values(1)
        batch = []
        for k, val in updates.items():
            if k not in headers:
                continue
            col = headers.index(k) + 1
            batch.append(gspread.Cell(row_index, col, str(val)))
        if batch:
            ws.update_cells(batch, value_input_option="USER_ENTERED")
