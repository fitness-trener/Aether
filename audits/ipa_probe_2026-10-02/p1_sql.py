import sqlite3
from flask import request

def build(name):
    return "SELECT * FROM users WHERE name = '" + name + "'"

def lookup(conn):
    q = build(request.args["name"])
    return conn.execute(q)          # computed call -> flagged?

def run(conn, sql):
    return conn.execute(sql)        # param -> flagged at helper?

def caller(conn):
    return run(conn, "SELECT 1")    # literal: safe
