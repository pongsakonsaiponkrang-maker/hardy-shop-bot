from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "HARDY SHOP ONLINE"

@app.route("/callback", methods=["POST"])
def callback():
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
