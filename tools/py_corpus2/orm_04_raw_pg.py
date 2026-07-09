import psycopg2

def fetch_active_users(dsn):
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute("SELECT id, email FROM users WHERE active = true")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [{"id": r[0], "email": r[1]} for r in rows]
