"""Study-domain models: syllabus, exams, availability and the generated plan."""

from datetime import datetime

from models.database import db


class Subject(db.Model):
    """A subject the student is preparing for."""

    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    color = db.Column(db.String(20), default="#6366f1")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    chapters = db.relationship(
        "Chapter", backref="subject", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}


class Chapter(db.Model):
    """A chapter / unit / topic node of the syllabus."""

    __tablename__ = "chapters"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    unit = db.Column(db.String(150), default="")
    name = db.Column(db.String(200), nullable=False)
    topics = db.Column(db.Text, default="")  # comma separated subtopics
    difficulty = db.Column(db.Integer, default=3)  # 1 (easy) .. 5 (hard)
    estimated_hours = db.Column(db.Float, default=2.0)
    priority = db.Column(db.Integer, default=3)  # 1 (low) .. 5 (critical)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject": self.subject.name if self.subject else "",
            "unit": self.unit,
            "name": self.name,
            "topics": self.topics,
            "difficulty": self.difficulty,
            "estimated_hours": self.estimated_hours,
            "priority": self.priority,
            "completed": self.completed,
        }


class Exam(db.Model):
    """An exam entry parsed from the timetable."""

    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"))
    subject_name = db.Column(db.String(150), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    exam_time = db.Column(db.String(20), default="09:00")
    duration_minutes = db.Column(db.Integer, default=180)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "exam_date": self.exam_date.isoformat(),
            "exam_time": self.exam_time,
            "duration_minutes": self.duration_minutes,
        }


class UnavailableDay(db.Model):
    """A date on which the student cannot study at all."""

    __tablename__ = "unavailable_days"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(120), default="Unavailable")

    def to_dict(self) -> dict:
        return {"id": self.id, "day": self.day.isoformat(), "reason": self.reason}


class Availability(db.Model):
    """Daily routine used to place study sessions in real clock time."""

    __tablename__ = "availability"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    wake_time = db.Column(db.String(5), default="07:00")
    sleep_time = db.Column(db.String(5), default="23:00")
    college_start = db.Column(db.String(5), default="")
    college_end = db.Column(db.String(5), default="")
    work_start = db.Column(db.String(5), default="")
    work_end = db.Column(db.String(5), default="")
    break_start = db.Column(db.String(5), default="13:00")
    break_end = db.Column(db.String(5), default="14:00")
    preferred_start = db.Column(db.String(5), default="17:00")
    max_daily_hours = db.Column(db.Float, default=6.0)
    session_minutes = db.Column(db.Integer, default=60)

    def to_dict(self) -> dict:
        return {
            c.name: getattr(self, c.name) for c in self.__table__.columns
        }


class TimetableTask(db.Model):
    """One scheduled block in the generated study timetable."""

    __tablename__ = "timetable"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(5), default="17:00")
    duration_minutes = db.Column(db.Integer, default=60)
    subject_name = db.Column(db.String(150), default="")
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"))
    chapter_name = db.Column(db.String(200), default="")
    task_type = db.Column(db.String(20), default="learning")  # learning/practice/revision/mock/final
    status = db.Column(db.String(20), default="pending")  # pending/completed
    position = db.Column(db.Integer, default=0)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "day": self.day.isoformat(),
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "subject_name": self.subject_name,
            "chapter_id": self.chapter_id,
            "chapter_name": self.chapter_name,
            "task_type": self.task_type,
            "status": self.status,
            "position": self.position,
        }


class StudySession(db.Model):
    """A completed focus session logged by the Pomodoro timer."""

    __tablename__ = "study_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    minutes = db.Column(db.Integer, default=25)
    mode = db.Column(db.String(20), default="pomodoro")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WeakTopic(db.Model):
    """A topic the analyzer flagged as weak (drives adaptive revision)."""

    __tablename__ = "weak_topics"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject_name = db.Column(db.String(150), default="")
    topic = db.Column(db.String(200), nullable=False)
    score = db.Column(db.Float, default=0.0)  # accuracy percentage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject_name": self.subject_name,
            "topic": self.topic,
            "score": self.score,
        }


class Reminder(db.Model):
    """Browser notification reminder configured by the user."""

    __tablename__ = "reminders"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(30), default="study")  # study/revision/mock/water/sleep
    time = db.Column(db.String(5), default="19:00")
    enabled = db.Column(db.Boolean, default=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "time": self.time, "enabled": self.enabled}
