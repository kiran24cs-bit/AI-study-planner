"""Regex fallbacks used when Groq is not configured or returns nothing.

These keep the upload flow useful in a fully offline environment.
"""

import re

from utils.date_utils import parse_date, parse_time

DATE_RE = re.compile(
    r"(\d{1,2}[-/ ][A-Za-z]{3,9}[-/ ]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
)
TIME_RE = re.compile(r"(\d{1,2}[:.]\d{2}\s*(?:AM|PM|am|pm)?)")


def heuristic_exams(text: str):
    """Pull `subject + date [+ time]` rows out of raw text."""
    exams = []
    for line in text.splitlines():
        line = line.strip()
        if len(line) < 4:
            continue
        date_match = DATE_RE.search(line)
        if not date_match:
            continue
        exam_date = parse_date(date_match.group(1))
        if not exam_date:
            continue
        time_match = TIME_RE.search(line)
        subject = DATE_RE.sub("", line)
        if time_match:
            subject = subject.replace(time_match.group(1), "")
        subject = re.sub(r"[|,;\t]+", " ", subject).strip(" -:\u2013")
        if not subject:
            subject = "Subject"
        exams.append(
            {
                "subject": subject[:120],
                "date": exam_date.isoformat(),
                "time": parse_time(time_match.group(1) if time_match else None),
                "duration_minutes": 180,
            }
        )
    return exams


def heuristic_syllabus(text: str):
    """Treat `Subject:` style headers as subjects and the rest as chapters."""
    subjects = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip(" \t-•*")
        if not line or len(line) < 3:
            continue
        is_header = line.endswith(":") or (line.isupper() and len(line) < 40)
        if is_header:
            current = {"name": line.rstrip(":").title()[:120], "chapters": []}
            subjects.append(current)
            continue
        if current is None:
            current = {"name": "General", "chapters": []}
            subjects.append(current)
        current["chapters"].append(
            {
                "unit": "",
                "name": line[:180],
                "topics": "",
                "difficulty": 3,
                "estimated_hours": 2.0,
                "priority": 3,
            }
        )
    return [s for s in subjects if s["chapters"]]
