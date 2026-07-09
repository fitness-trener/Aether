from flask import Flask, request, jsonify
import redis

app = Flask(__name__)
cache = redis.Redis(host="localhost", port=6379)

@app.route("/orders/<order_id>")
def get_order(order_id):
    cached = cache.get("order:" + order_id)
    if cached:
        return jsonify({"id": order_id, "cached": True})
    return jsonify({"id": order_id, "cached": False})
