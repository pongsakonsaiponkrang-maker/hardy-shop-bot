# HARDY Shop Bot V3.1 (Production Safe)

## 1) Environment Variables
ตั้งค่าในเครื่องหรือ Render:

- LINE_CHANNEL_ACCESS_TOKEN
- LINE_CHANNEL_SECRET
- ADMIN_USER_IDS (optional) เช่น: Uxxxxxxxx,Uyyyyyyyy
- SHEET_ID

Google service account:
- GOOGLE_SERVICE_ACCOUNT_JSON (แนะนำ) ใส่ JSON ทั้งก้อน
  หรือ
- GOOGLE_SERVICE_ACCOUNT_FILE=/path/sa.json

Business:
- DEFAULT_PRICE_THB=1290
- SESSION_TTL_SECONDS=1800

Worksheet names (optional):
- WS_STOCK=HARDY_STOCK
- WS_SESSION=HARDY_SESSION
- WS_ORDER=HARDY_ORDER

## 2) Google Sheet format
สร้าง Spreadsheet แล้วแชร์ให้ service account email (Editor)

### HARDY_STOCK
Header:
color | size | stock | price

ตัวอย่าง:
Navy | M | 10 | 1290
Dark Coffee | L | 5 | 1290

### HARDY_SESSION
ระบบสร้างเอง (auto)

### HARDY_ORDER
ระบบสร้างเอง (auto)

## 3) Run
```bash
pip install -r requirements.txt
python app.py
