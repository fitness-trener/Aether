import pandas as pd

def aggregate(df, group_col, value_cols):
    out = {}
    for col in value_cols:
        out[col] = df.groupby(group_col)[col].mean()
    return pd.DataFrame(out)
