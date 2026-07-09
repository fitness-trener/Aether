from flask import Flask, request, session
import hashlib

app = Flask(__name__)
app.secret_key = "change-me"

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    digest = hashlib.sha256(password.encode()).hexdigest()
    session["user"] = username
    return {"token": digest[:16]}
