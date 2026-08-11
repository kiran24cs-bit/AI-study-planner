"""Slot scheduler: turns a daily routine into concrete free time blocks."""

from utils.date_utils import minutes_from_time, time_from_minutes


def _busy_ranges(availability):
    """Collect the minute ranges the student is NOT free."""
    ranges = []
    pairs = [
        (availability.college_start, availability.college_end),
        (availability.work_start, availability.work_end),
        (availability.break_start, availability.break_end),
    ]
    for start, end in pairs:
        if start and end:
            s, e = minutes_from_time(start), minutes_from_time(end)
            if e > s:
                ranges.append((s, e))
    return sorted(ranges)


def free_slots(availability):
    """Return free (start, end) minute ranges between wake and sleep time."""
    day_start = minutes_from_time(availability.preferred_start or availability.wake_time)
    day_end = minutes_from_time(availability.sleep_time or "23:00")
    if day_end <= day_start:
        day_end = 23 * 60

    slots = []
    cursor = day_start
    for busy_start, busy_end in _busy_ranges(availability):
        if busy_end <= cursor:
            continue
        if busy_start > cursor:
            slots.append((cursor, min(busy_start, day_end)))
        cursor = max(cursor, busy_end)
        if cursor >= day_end:
            break
    if cursor < day_end:
        slots.append((cursor, day_end))

    return [(s, e) for s, e in slots if e - s >= 20]


def build_day_slots(availability):
    """Split the free ranges into study sessions capped by max daily hours.

    Returns a list of (start_time_string, duration_minutes).
    """
    session = int(availability.session_minutes or 60)
    session = max(20, min(session, 180))
    budget = int(float(availability.max_daily_hours or 6) * 60)

    blocks = []
    for start, end in free_slots(availability):
        cursor = start
        while cursor + session <= end and budget >= session:
            blocks.append((time_from_minutes(cursor), session))
            cursor += session + 10  # 10 minute breather between sessions
            budget -= session
        if budget < session:
            break
    return blocks
