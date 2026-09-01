# Imports the frontend could not see (BUGS.md BUG-011).
#
# The optional-dependency guard is universal in frameworks:
#
#     try:
#         import yaml
#     except ImportError:
#         raise ImportError("pip install pyyaml")
#
# `py_to_ir` used to register imports only as direct children of the
# module body, so everything under `try:` — and every function-local
# import — was invisible. An unresolved `yaml.load(raw)` is not
# over-flagged; it is SILENT: the qualified-sink table never matches, the
# guard table never matches, and `load` is not a method-name sink. Same
# for `pickle.loads`. Fifteen agent frameworks import SQLAlchemy this way,
# which is also why BUG-010's first fix cleared so little.
#
# The ambiguity rule that comes with the fix: a local name bound by two
# imports to DIFFERENT targets resolves to nothing. It clears nothing and
# it sinks nothing — never pick a winner, the error direction of guessing
# is a false accept.

try:
    import pickle
    import yaml
    from sqlalchemy.sql.expression import select, text
except ImportError:  # pragma: no cover
    raise ImportError("optional dependencies")

try:
    from sqlalchemy import update
except ImportError:
    from mylib.compat import update


# --- the sinks that were silent ----------------------------------------

def load_guarded_yaml(raw):
    return yaml.load(raw)                                   # CWE-502


def unpickle_guarded(blob):
    return pickle.loads(blob)                               # CWE-502


def load_in_function_scope(raw):
    import marshal
    return marshal.loads(raw)                               # CWE-502


# --- the same guard resolves the SQL builders too -----------------------

def guarded_select(conn, t, cid):
    return conn.execute(select(t).where(t.c.id == cid))


def guarded_text_literal(conn):
    conn.execute(text("SELECT 1"))


# --- ambiguous alias: two imports, two targets, no winner ---------------

def ambiguous_update_is_not_a_builder(conn, t, cid):
    # `update` is sqlalchemy's or mylib's; the frontend cannot know which,
    # so the result is still a computed query.
    return conn.execute(update(t).where(t.c.id == cid))     # over-flag, by design


def guarded_yaml_safe(raw):
    return yaml.safe_load(raw)
