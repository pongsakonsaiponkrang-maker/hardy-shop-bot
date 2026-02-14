# core/config.py

import os
from dotenv import load_dotenv

load_dotenv()

# ---------------- LINE ----------------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "").strip()

# ---------------- GOOGLE SHEET ----------------
SHEET_ID = os.getenv("SHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

# ---------------- ADMIN ----------------
ADMIN_USER_IDS = [
    x.strip()
    for x in os.getenv("ADMIN_USER_IDS", "").split(",")
    if x.strip()
]

# ---------------- BUSINESS CONFIG ----------------
LOW_STOCK_ALERT = int(os.getenv("LOW_STOCK_ALERT", "3"))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))

# ---------------- APP ----------------
APP_NAME = "HARDY PRO BOT"