# Real-world shape — SQL injection via string-built query (CWE-89).
#
# The DB-API is universal across Python: sqlite3, psycopg2, pymysql and
# every ORM's raw-SQL escape hatch expose `cursor.execute(sql, params)`.
# The bug is always the same: the value is concatenated (or f-stringed)
# into the SQL text instead of being passed as a bound parameter, so
# `1 OR 1=1--` changes the query's meaning rather than its data.
#
# CWE-89. Directly analogous, already ported in this repo:
#   - CVE-2026-1312 (Django order_by injection) — see
#     bench/realworld_cve/cve_2026_1312_django_orderby_vulnerable.aeth
#
# The vulnerable shape:

import sqlite3


def find_user(cur, name: str):
    # `name` is user-controlled; concatenation puts it in the SQL text.
    return cur.execute("SELECT * FROM users WHERE name = '" + name + "'")


def find_user_fstring(cur, uid: str):
    # Identical hazard, modern spelling. This is the shape that dominates
    # AI-generated Python.
    return cur.execute(f"SELECT * FROM users WHERE id = {uid}")


# The fix the DB-API ships: parameter binding. The driver sends the SQL
# and the values separately, so no value can alter the statement.

def find_user_safe(cur, name: str):
    return cur.execute("SELECT * FROM users WHERE name = ?", (name,))


# In Aether this maps 1:1 onto E0713:
#   cur.execute("... '" + name + "'")     <-> sqlQuery("..." + name)          -> E0713
#   cur.execute("... = ?", (name,))       <-> sqlQuery(sqlBind("... ?", name)) -> clean
