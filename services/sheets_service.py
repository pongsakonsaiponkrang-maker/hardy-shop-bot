# services/sheets_service.py

import json
import gspread
from google.oauth2.service_account import Credentials

from core.config import SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON

_gc = None
_spreadsheet = None

_sheet_orders = None
_sheet_sessions = None
_sheet_stock = None


def _init_connection():
    """
    Initialize Google Sheets connection (singleton)
    """
    global _gc, _spreadsheet

    if _gc:
        return

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("Missing GOOGLE_SERVICE_ACCOUNT_JSON")

    if not SHEET_ID:
        raise RuntimeError("Missing SHEET_ID")

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    creds = Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )

    _gc = gspread.authorize(creds)
    _spreadsheet = _gc.open_by_key(SHEET_ID)


def get_orders_sheet():
    global _sheet_orders
    _init_connection()

    if not _sheet_orders:
        _sheet_orders = _spreadsheet.worksheet("HARDY_ORDER")

    return _sheet_orders


def get_sessions_sheet():
    global _sheet_sessions
    _init_connection()

    if not _sheet_sessions:
        _sheet_sessions = _spreadsheet.worksheet("HARDY_SESSION")

    return _sheet_sessions


def get_stock_sheet():
    global _sheet_stock
    _init_connection()

    if not _sheet_stock:
        _sheet_stock = _spreadsheet.worksheet("HARDY_STOCK")

    return _sheet_stock