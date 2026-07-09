import pandas as pd

def convert(src_csv, dest_parquet):
    df = pd.read_csv(src_csv)
    df.to_parquet(dest_parquet)
    return dest_parquet
