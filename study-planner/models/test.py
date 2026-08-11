"""Assessment models: tests, questions, answers, scores and performance rows."""

from datetime import datetime

from models.database import db


class Test(db.Model):
    """An AI-generated MCQ test for a completed chapter."""

    __tablename__ = "tests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapters.id"))
    subject_name = db.Column(db.String(150), default="")
    chapter_name = db.Column(db.String(200), default="")
    duration_minutes = db.Column(db.Integer, default=20)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted = db.Column(db.Boolean, default=False)

    questions = db.relationship(
        "Question", backref="test", cascade="all, delete-orphan", lazy="dynamic"
    )

    def to_dict(self, include_answers=False) -> dict:
        return {
            "id": self.id,
            "subject_name": self.subject_name,
            "chapter_name": self.chapter_name,
            "duration_minutes": self.duration_minutes,
            "submitted": self.submitted,
            "questions": [q.to_dict(include_answers) for q in self.questions],
        }


class Question(db.Model):
    """A single MCQ."""

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text, default="")
    option_b = db.Column(db.Text, default="")
    option_c = db.Column(db.Text, default="")
    option_d = db.Column(db.Text, default="")
    correct_option = db.Column(db.String(1), default="A")
    difficulty = db.Column(db.String(10), default="medium")
    explanation = db.Column(db.Text, default="")
    topic = db.Column(db.String(200), default="")

    def to_dict(self, include_answers=False) -> dict:
        data = {
            "id": self.id,
            "text": self.text,
            "options": {
                "A": self.option_a,
                "B": self.option_b,
                "C": self.option_c,
                "D": self.option_d,
            },
            "difficulty": self.difficulty,
            "topic": self.topic,
        }
        if include_answers:
            data["correct_option"] = self.correct_option
            data["explanation"] = self.explanation
        return data


class Answer(db.Model):
    """The student's response to a question."""

    __tablename__ = "answers"

    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    selected_option = db.Column(db.String(1))  # None => skipped
    is_correct = db.Column(db.Boolean, default=False)
    seconds_spent = db.Column(db.Integer, default=0)


class Score(db.Model):
    """Aggregated result of one submitted test."""

    __tablename__ = "scores"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    test_id = db.Column(db.Integer, db.ForeignKey("tests.id"), nullable=False)
    subject_name = db.Column(db.String(150), default="")
    chapter_name = db.Column(db.String(200), default="")
    total = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    wrong = db.Column(db.Integer, default=0)
    skipped = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0.0)
    accuracy = db.Column(db.Float, default=0.0)
    speed = db.Column(db.Float, default=0.0)  # seconds per question
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "test_id": self.test_id,
            "subject_name": self.subject_name,
            "chapter_name": self.chapter_name,
            "total": self.total,
            "correct": self.correct,
            "wrong": self.wrong,
            "skipped": self.skipped,
            "percentage": round(self.percentage, 2),
            "accuracy": round(self.accuracy, 2),
            "speed": round(self.speed, 2),
            "created_at": self.created_at.isoformat(),
        }


class Performance(db.Model):
    """Daily rollup used by the performance charts."""

    __tablename__ = "performance"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    study_minutes = db.Column(db.Integer, default=0)
    tasks_completed = db.Column(db.Integer, default=0)
    avg_score = db.Column(db.Float, default=0.0)

    def to_dict(self) -> dict:
        return {
            "day": self.day.isoformat(),
            "study_minutes": self.study_minutes,
            "tasks_completed": self.tasks_completed,
            "avg_score": round(self.avg_score, 2),
        }
