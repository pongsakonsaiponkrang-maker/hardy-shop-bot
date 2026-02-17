import os
import json

def env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

APP_NAME = "HARDY SHOP BOT"
APP_VERSION = "3.1"

LINE_CHANNEL_ACCESS_TOKEN = env("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = env("LINE_CHANNEL_SECRET")

# Admins (LINE userId) comma separated
ADMIN_USER_IDS = [x.strip() for x in env("ADMIN_USER_IDS").split(",") if x.strip()]

# Google Sheets
SHEET_ID = env("SHEET_ID")

# Either:
# 1) GOOGLE_SERVICE_ACCOUNT_JSON = '{"type": "...", ...}'
# 2) GOOGLE_SERVICE_ACCOUNT_FILE = '/path/sa.json'
GOOGLE_SERVICE_ACCOUNT_JSON = env("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_SERVICE_ACCOUNT_FILE = env("GOOGLE_SERVICE_ACCOUNT_FILE")

# Business
DEFAULT_PRICE_THB = int(env("DEFAULT_PRICE_THB", "1290"))

# Session
SESSION_TTL_SECONDS = int(env("SESSION_TTL_SECONDS", "1800"))

# Worksheets name
WS_STOCK = env("WS_STOCK", "HARDY_STOCK")
WS_SESSION = env("WS_SESSION", "HARDY_SESSION")
WS_ORDER = env("WS_ORDER", "HARDY_ORDER")

# Quick Reply limit (LINE)
QUICK_REPLY_LIMIT = int(env("QUICK_REPLY_LIMIT", "13"))
# ADMIN (comma separated)
ADMIN_USER_IDS = [x.strip() for x in env("ADMIN_USER_IDS", "").split(",") if x.strip()]
