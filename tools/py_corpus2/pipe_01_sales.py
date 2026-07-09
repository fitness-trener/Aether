import pandas as pd

def monthly_revenue(csv_path):
    df = pd.read_csv(csv_path)
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    return df.groupby("month")["amount"].sum().to_dict()
