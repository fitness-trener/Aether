# SQLAlchemy Core expressions at a SQL sink (BUGS.md BUG-010).
#
# `conn.execute(select(t).where(t.c.id == cid))` is the SAFEST form of SQL
# in Python: the expression object is compiled by SQLAlchemy with bound
# parameters, and no string is concatenated anywhere. Before the fix,
# Aether refused it as "a computed call" — `execute` is a sink by method
# name and any non-literal argument read as dynamic — so every ORM call
# site was a finding: 1,029 of 1,055 findings across 15 agent frameworks
# (bench/framework_scan/REPORT.md).
#
# The soundness line that must NOT move: `text(...)` and `literal_column(...)`
# are where raw SQL strings re-enter the expression language. A concatenated
# argument to either is a real injection and must still be refused, even
# nested inside an otherwise-safe `select(...)`.

import sqlalchemy as sa
from sqlalchemy import select, insert, delete, text, literal_column
from mylib.sql import compose


# --- SAFE: expression builders with bound parameters -------------------

def orm_select(conn, t, cid):
    return conn.execute(select(t).where(t.c.id == cid))


def orm_delete(conn, t, now):
    conn.execute(delete(t).where(t.c.expires_at < now))


def orm_insert(conn, t, name):
    conn.execute(insert(t).values(name=name))


def orm_aliased_module(conn, t, cid):
    # `import sqlalchemy as sa` — the alias must resolve to the same root.
    return conn.execute(sa.select(t).where(t.c.id == cid))


def orm_chained_first(conn, t, cid):
    # The exact shape the framework scan hit most: a call used as RECEIVER.
    return conn.execute(select(t.c.meta).where(t.c.id == cid)).first()


def text_literal(conn):
    conn.execute(text("SELECT 1"))


def text_bound_params(conn, uid):
    # Named bind parameters: the literal is fixed, the value travels separately.
    return conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": uid})


def stmt_bound_elsewhere(conn, t, cid):
    # The expression built in one statement and executed in another.
    stmt = select(t).where(t.c.id == cid)
    return conn.execute(stmt)


def stmt_built_incrementally(conn, t, cid, limit):
    # The dominant shape in real ORM code: bound, then rebound to a method
    # on itself. Anchored at `select(t)`; every rebinding stays rooted there.
    stmt = select(t)
    if cid is not None:
        stmt = stmt.where(t.c.id == cid)
    stmt = stmt.limit(limit)
    return conn.execute(stmt).fetchall()


def table_method_form(conn, t, run_id):
    # SQLAlchemy's Table API: the root takes NO positional argument, so no
    # raw string can enter through it.
    conn.execute(t.delete().where(t.c.run_id == run_id))
    conn.execute(t.update().where(t.c.run_id == run_id).values(done=True))


def text_of_literal_name(conn, schema):
    # Raw-entry argument is a NAME bound only to a literal; the value the
    # caller controls travels as a bind parameter.
    sql_query = "SELECT 1 FROM information_schema.tables WHERE table_schema = :s"
    return conn.execute(text(sql_query), {"s": schema})


# --- VULNERABLE: raw SQL strings re-entering through text()/literal_column() ---

def text_concat(conn, uid):
    return conn.execute(text("SELECT * FROM users WHERE id = " + uid))      # CWE-89


def text_fstring(conn, uid):
    return conn.execute(text(f"SELECT * FROM users WHERE id = {uid}"))      # CWE-89


def nested_text_concat(conn, t, name):
    # Safe builder on the outside, injection on the inside.
    return conn.execute(select(t).where(text("name = '" + name + "'")))     # CWE-89


def literal_column_concat(conn, t, col):
    return conn.execute(select(literal_column("id, " + col)).select_from(t))  # CWE-89


def unknown_builder_concat(conn, q):
    # A NAME may not clear a call: `compose` is not a SQLAlchemy builder, so
    # its result is still a computed query.
    return conn.execute(compose("SELECT * FROM t WHERE " + q))              # CWE-89


def stmt_rebound_to_raw_text(conn, t, name):
    # Anchored at select(t), but a rebinding carries a concatenated raw
    # string: one bad binding disqualifies the name for every use.
    stmt = select(t)
    stmt = stmt.where(text("name = '" + name + "'"))
    return conn.execute(stmt)                                              # CWE-89


def table_method_with_string_arg(conn, qb, q):
    # `.select(...)` on an unknown receiver WITH an argument is not the
    # Table form — a builder that returns a raw string has to be handed one.
    return conn.execute(qb.select("SELECT * FROM t WHERE " + q))            # CWE-89


def text_of_parameter(conn, sql_query):
    # The name is a PARAMETER, bound nowhere in this function: unresolvable.
    return conn.execute(text(sql_query))                                   # CWE-89


def unanchored_self_chain(conn, a, b):
    # Two parameters rebound to methods on each other: no anchor, so
    # neither name ever qualifies, however the chain is spelled.
    a = b.where(True)
    b = a.where(True)
    return conn.execute(a)                                                 # CWE-89


def raw_concat(conn, name):
    # The original shape, unchanged by any of this.
    return conn.execute("SELECT * FROM users WHERE name = '" + name + "'")  # CWE-89
