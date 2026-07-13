import re
from datetime import timedelta

def parse_timedelta(time_str: str) -> timedelta | None:
    match = re.match(r"(\d+)([mhd])$", time_str.lower())
    if not match:
        return None

    value, unit = match.groups()
    value = int(value)

    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)

    return None
