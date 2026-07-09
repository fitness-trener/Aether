from datetime import datetime, timedelta

def business_days_between(start, end):
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    return days

def format_timestamp(fmt="%Y-%m-%d %H:%M"):
    return datetime.now().strftime(fmt)
