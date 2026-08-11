"""Date / time helper functions shared by the planner and scheduler."""

from datetime import date, datetime, timedelta
import re

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d %Y",
    "%B %d %Y",
    "%d-%b-%Y",
]


def parse_date(value):
    """Parse a date from many common formats. Returns None when unparseable."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip().replace(",", "")
    for pattern in DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def parse_time(value, fallback="09:00"):
    """Normalise a time string to 24h HH:MM."""
    if not value:
        return fallback
    text = str(value).strip().upper().replace(".", ":")
    match = re.match(r"^(\d{1,2}):?(\d{2})?\s*(AM|PM)?$", text)
    if not match:
        return fallback
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)
    if meridiem == "PM" and hour < 12:
        hour += 12
    if meridiem == "AM" and hour == 12:
        hour = 0
    hour = max(0, min(hour, 23))
    minute = max(0, min(minute, 59))
    return f"{hour:02d}:{minute:02d}"


def minutes_from_time(hhmm: str) -> int:
    """Convert 'HH:MM' to minutes since midnight."""
    try:
        hours, minutes = hhmm.split(":")
        return int(hours) * 60 + int(minutes)
    except (ValueError, AttributeError):
        return 0


def time_from_minutes(total_minutes: int) -> str:
    """Convert minutes since midnight to 'HH:MM' (wrapping at 24h)."""
    total_minutes = max(0, min(total_minutes, 24 * 60 - 1))
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def date_range(start: date, end: date):
    """Yield every date from start to end inclusive."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def days_until(target: date) -> int:
    """Whole days from today until target (never negative)."""
    return max((target - date.today()).days, 0)
