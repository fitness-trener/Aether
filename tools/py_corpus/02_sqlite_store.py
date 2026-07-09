import sqlite3

def connect(path):
    return sqlite3.connect(path)

def get_order(conn, order_id):
    cur = conn.cursor()
    cur.execute("SELECT id, total FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    return {"id": row[0], "total": row[1]} if row else None

def insert_order(conn, total):
    cur = conn.cursor()
    cur.execute("INSERT INTO orders (total) VALUES (?)", (total,))
    conn.commit()
    return cur.lastrowid
