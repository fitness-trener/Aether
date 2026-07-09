from sqlalchemy import create_engine, text

def apply_migration(url, sql_file):
    engine = create_engine(url)
    with open(sql_file) as fh:
        sql = fh.read()
    with engine.begin() as conn:
        for statement in sql.split(";"):
            if statement.strip():
                conn.execute(text(statement))
