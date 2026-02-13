from flask import Flask, request
import json
import datetime

app = Flask(__name__)

# ====== MEMORY (เก็บ state ลูกค้า) ======
user_state = {}

COLORS = ["Dark Coffee", "Navy"]
SIZES = ["XS", "S", "M", "L", "XL"]

# ====== HOME ======
@app.route("/")
def home():
    return "HARDY SHOP V4 ONLINE"

# ====== CALLBACK ======
@app.route("/callback", methods=["POST"])
def callback():

    data = request.json
    events = data.get("events", [])

    for event in events:

        if event["type"] != "message":
            continue

        user_id = event["source"]["userId"]
        msg = event["message"]["text"].strip()

        # ===== เริ่มสั่งซื้อ =====
        if msg == "สั่งซื้อ":

            user_state[user_id] = {"step": "choose_color"}

            print("SEND COLOR MENU")
            print("Dark Coffee / Navy")

        # ===== เลือกสี =====
        elif msg in COLORS:

            if user_id not in user_state:
                continue

            user_state[user_id]["color"] = msg
            user_state[user_id]["step"] = "choose_size"

            print("SEND SIZE MENU")
            print(SIZES)

        # ===== เลือกไซส์ =====
        elif msg in SIZES:

            if user_id not in user_state:
                continue

            user_state[user_id]["size"] = msg
            user_state[user_id]["step"] = "get_address"

            print("ASK CUSTOMER ADDRESS")

        # ===== รับที่อยู่ =====
        else:

            if user_id in user_state and user_state[user_id]["step"] == "get_address":

                order = user_state[user_id]

                print("SAVE TO GOOGLE SHEET")
                print({
                    "DATE": str(datetime.datetime.now()),
                    "USER_ID": user_id,
                    "COLOR": order["color"],
                    "SIZE": order["size"],
                    "ADDRESS": msg,
                    "STATUS": "NEW"
                })

                del user_state[user_id]

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
