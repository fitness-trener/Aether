from pymongo import MongoClient
import os

client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017"))
db = client.analytics

def record_event(name, props):
    db.events.insert_one({"name": name, "props": props})

def count_events(name):
    return db.events.count_documents({"name": name})
