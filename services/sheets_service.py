# ==========================================================
# HARDY SHEETS SERVICE - CLEAN VERSION
# ==========================================================

import json
import gspread
from google.oauth2.service_account import Credentials
from core.config import GOOGLE_SERVICE_ACCOUNT_JSON, SHEET_ID

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_creds = Credentials.from_service_account_info(
    json.loads(GOOGLE_SERVICE_ACCOUNT_JSON),
    scopes=SCOPES,
)

_client = gspread.authorize(_creds)
_sheet = _client.open_by_key(SHEET_ID)


def get_ws(ws_name):
    return _sheet.worksheet(ws_name)


def get_all_records(ws_name):
    return get_ws(ws_name).get_all_records()


def append_row(ws_name, row):
    get_ws(ws_name).append_row(row, value_input_option="USER_ENTERED")


def update_row(ws_name, row_index, row_values):
    get_ws(ws_name).update(f"A{row_index}", [row_values])


def find_row_by_value(ws_name, column_name, value):
    ws = get_ws(ws_name)
    records = ws.get_all_records()

    for idx, r in enumerate(records, start=2):
        if str(r.get(column_name)).strip() == str(value).strip():
            return idx

    return None
