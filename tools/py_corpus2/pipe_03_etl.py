import pandas as pd
from sqlalchemy import create_engine

def load_to_warehouse(csv_path, table, db_url):
    df = pd.read_csv(csv_path)
    df = df.dropna()
    engine = create_engine(db_url)
    df.to_sql(table, engine, if_exists="append", index=False)
    return len(df)
