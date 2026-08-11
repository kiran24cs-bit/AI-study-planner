"""The study planner engine.

Builds a full day-by-day timetable from exams, syllabus, unavailable days and
the student's daily availability. Also supports partial regeneration and
adaptive re-planning driven by test scores.
"""

from datetime import date, timedelta

from config import Config
from models.database import db
from models.study import (
    Availability,
    Chapter,
    Exam,
    Subject,
    TimetableTask,
    UnavailableDay,
    WeakTopic,
)
from services.scheduler import build_day_slots
from utils.date_utils import date_range


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def get_availability(user_id: int) -> Availability:
    """Fetch the user's routine, creating sane defaults on first use."""
    availability = Availability.query.filter_by(user_id=user_id).first()
    if not availability:
        availability = Availability(user_id=user_id)
        db.session.add(availability)
        db.session.commit()
    return availability


def _blocked_days(user_id: int):
    return {d.day for d in UnavailableDay.query.filter_by(user_id=user_id).all()}


def _exam_days(user_id: int):
    return {e.exam_date: e for e in Exam.query.filter_by(user_id=user_id).all()}


def _weak_topic_names(user_id: int):
    return {w.topic.lower() for w in WeakTopic.query.filter_by(user_id=user_id).all()}


def _chapter_weight(chapter: Chapter, weak_names) -> float:
    """Higher weight => scheduled earlier and given more sessions."""
    weight = (chapter.priority or 3) * 1.5 + (chapter.difficulty or 3)
    if chapter.name.lower() in weak_names:
        weight += 4
    return weight


def _sessions_for(chapter: Chapter, session_minutes: int, weak_names) -> int:
    """How many blocks this chapter needs (learning + practice + revision)."""
    hours = float(chapter.estimated_hours or 2.0)
    base = max(1, round((hours * 60) / max(session_minutes, 20)))
    if chapter.name.lower() in weak_names:
        base += 1
    return base


# --------------------------------------------------------------------------
# Plan generation
# --------------------------------------------------------------------------

def generate_plan(user_id: int, clear_existing: bool = True) -> dict:
    """Create the full study timetable for a user.

    Returns a summary dict: {days, tasks, message}.
    """
    availability = get_availability(user_id)
    exams = Exam.query.filter_by(user_id=user_id).order_by(Exam.exam_date).all()
    if not exams:
        return {"days": 0, "tasks": 0, "message": "Add at least one exam first."}

    subjects = Subject.query.filter_by(user_id=user_id).all()
    if not subjects:
        return {"days": 0, "tasks": 0, "message": "Add your syllabus first."}

    if clear_existing:
        TimetableTask.query.filter_by(user_id=user_id).delete()
        db.session.commit()

    start = date.today()
    last_exam = exams[-1].exam_date
    if last_exam < start:
        return {"days": 0, "tasks": 0, "message": "All exam dates are in the past."}

    blocked = _blocked_days(user_id)
    exam_map = _exam_days(user_id)
    weak_names = _weak_topic_names(user_id)
    slots_template = build_day_slots(availability)
    if not slots_template:
        return {"days": 0, "tasks": 0, "message": "No free time found in your routine."}

    session_minutes = int(availability.session_minutes or Config.DEFAULT_SESSION_MINUTES)

    # Build the work queue: one entry per required session, ordered by exam
    # date first, then by weight (priority + difficulty + weakness).
    exam_date_by_subject = {e.subject_name.lower(): e.exam_date for e in exams}
    queue = []
    for subject in subjects:
        deadline = exam_date_by_subject.get(subject.name.lower(), last_exam)
        for chapter in subject.chapters.filter_by(completed=False).all():
            count = _sessions_for(chapter, session_minutes, weak_names)
            weight = _chapter_weight(chapter, weak_names)
            for index in range(count):
                # Session mix: learn first, then practice, then revise.
                if index == 0:
                    kind = "learning"
                elif index < count - 1:
                    kind = "practice"
                else:
                    kind = "revision"
                queue.append(
                    {
                        "deadline": deadline,
                        "weight": weight,
                        "subject": subject.name,
                        "chapter": chapter,
                        "kind": kind,
                    }
                )

    queue.sort(key=lambda item: (item["deadline"], -item["weight"]))

    created = 0
    used_days = set()
    cursor = 0

    for day in date_range(start, last_exam):
        if day in blocked:
            continue

        # Exam day: only a light final revision in the morning.
        if day in exam_map:
            exam = exam_map[day]
            db.session.add(
                TimetableTask(
                    user_id=user_id,
                    day=day,
                    start_time=availability.wake_time or "07:00",
                    duration_minutes=60,
                    subject_name=exam.subject_name,
                    chapter_name="Final revision before exam",
                    task_type="final",
                    position=0,
                )
            )
            created += 1
            used_days.add(day)
            continue

        for position, (start_time, duration) in enumerate(slots_template):
            if cursor >= len(queue):
                break
            item = queue[cursor]
            # Never schedule a chapter after its own exam.
            if item["deadline"] < day:
                cursor += 1
                continue
            chapter = item["chapter"]
            db.session.add(
                TimetableTask(
                    user_id=user_id,
                    day=day,
                    start_time=start_time,
                    duration_minutes=duration,
                    subject_name=item["subject"],
                    chapter_id=chapter.id,
                    chapter_name=chapter.name,
                    task_type=item["kind"],
                    position=position,
                )
            )
            created += 1
            used_days.add(day)
            cursor += 1

    # Reserve the buffer days before each exam for mock tests.
    _add_mock_tests(user_id, exams, blocked, availability)
    db.session.commit()

    return {
        "days": len(used_days),
        "tasks": created,
        "message": f"Generated {created} tasks across {len(used_days)} days.",
    }


def _add_mock_tests(user_id, exams, blocked, availability):
    """Insert a mock test block a couple of days before every exam."""
    for exam in exams:
        target = exam.exam_date - timedelta(days=Config.BUFFER_DAYS_BEFORE_EXAM)
        if target < date.today() or target in blocked:
            continue
        exists = TimetableTask.query.filter_by(
            user_id=user_id, day=target, task_type="mock", subject_name=exam.subject_name
        ).first()
        if exists:
            continue
        db.session.add(
            TimetableTask(
                user_id=user_id,
                day=target,
                start_time=availability.preferred_start or "17:00",
                duration_minutes=60,
                subject_name=exam.subject_name,
                chapter_name=f"Mock test — {exam.subject_name}",
                task_type="mock",
                position=99,
            )
        )


def regenerate_day(user_id: int, day: date) -> dict:
    """Rebuild a single day using the highest-weight pending chapters."""
    availability = get_availability(user_id)
    TimetableTask.query.filter_by(user_id=user_id, day=day, status="pending").delete()
    db.session.commit()

    weak_names = _weak_topic_names(user_id)
    pending = (
        Chapter.query.join(Subject)
        .filter(Subject.user_id == user_id, Chapter.completed.is_(False))
        .all()
    )
    pending.sort(key=lambda c: -_chapter_weight(c, weak_names))
    if not pending:
        return {"tasks": 0, "message": "No pending chapters left."}

    slots = build_day_slots(availability)
    created = 0
    for position, (start_time, duration) in enumerate(slots):
        chapter = pending[position % len(pending)]
        db.session.add(
            TimetableTask(
                user_id=user_id,
                day=day,
                start_time=start_time,
                duration_minutes=duration,
                subject_name=chapter.subject.name,
                chapter_id=chapter.id,
                chapter_name=chapter.name,
                task_type="revision" if position % 3 == 2 else "learning",
                position=position,
            )
        )
        created += 1
    db.session.commit()
    return {"tasks": created, "message": f"Rebuilt {day.isoformat()} with {created} tasks."}


def adapt_after_test(user_id: int, score) -> str:
    """Adaptive planner: react to the latest test score.

    Low score  -> add extra revision blocks for that chapter.
    High score -> drop redundant revision blocks and add advanced practice.
    """
    availability = get_availability(user_id)
    tomorrow = date.today() + timedelta(days=1)
    blocked = _blocked_days(user_id)
    while tomorrow in blocked:
        tomorrow += timedelta(days=1)

    if score.percentage < 60:
        for offset in (0, 2):
            db.session.add(
                TimetableTask(
                    user_id=user_id,
                    day=tomorrow + timedelta(days=offset),
                    start_time=availability.preferred_start or "17:00",
                    duration_minutes=int(availability.session_minutes or 60),
                    subject_name=score.subject_name,
                    chapter_name=f"Extra revision — {score.chapter_name}",
                    task_type="revision",
                    position=50 + offset,
                )
            )
        db.session.commit()
        return "Score below 60% — added two extra revision sessions."

    if score.percentage >= 85:
        removed = TimetableTask.query.filter_by(
            user_id=user_id,
            chapter_name=score.chapter_name,
            task_type="revision",
            status="pending",
        ).delete()
        db.session.add(
            TimetableTask(
                user_id=user_id,
                day=tomorrow,
                start_time=availability.preferred_start or "17:00",
                duration_minutes=int(availability.session_minutes or 60),
                subject_name=score.subject_name,
                chapter_name=f"Advanced practice — {score.chapter_name}",
                task_type="practice",
                position=51,
            )
        )
        db.session.commit()
        return f"Strong score — removed {removed} revision blocks, added advanced practice."

    return "Score on track — plan unchanged."
