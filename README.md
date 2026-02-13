# HARDY PRO - LINE Order Bot

## Features
- LINE Webhook + Reply
- Google Sheet Order logging
- Session flow: color -> size -> qty -> name -> phone -> address -> confirm
- Admin notify (optional)

## Google Sheet
Create spreadsheet with 2 sheets:
- HARDY_ORDER (or set ORDERS_SHEET_NAME)
- SESSIONS (or set SESSIONS_SHEET_NAME)

Orders headers:
DATE | ORDER_ID | USER_ID | NAME | PHONE | ADDRESS | COLOR | SIZE | QTY | AMOUNT | STATUS

Sessions headers:
UPDATED_AT | USER_ID | STATE | DATA_JSON | EXPIRE_AT

Share spreadsheet to service account email (Editor).

## Environment Variables (Render)
- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- SHEET_ID
- ORDERS_SHEET_NAME=HARDY_ORDER
- SESSIONS_SHEET_NAME=SESSIONS
- GOOGLE_SERVICE_ACCOUNT_JSON   (paste full JSON key)
- ADMIN_USER_ID (optional)
- PRICE_PER_PIECE=1290 (optional)
- SESSION_TTL=1800 (optional)

## Run locally
pip install -r requirements.txt
python app.py

## Render Deploy
Start command:
gunicorn app:app --bind 0.0.0.0:$PORT

## LINE Webhook URL
https://YOUR-RENDER-URL/callback
Enable webhook + Verify
