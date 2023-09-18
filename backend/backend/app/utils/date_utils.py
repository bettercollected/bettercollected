from datetime import datetime


def get_formatted_date_from_str(dt_str):
    return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ")
