"""User model + authentication helpers."""

from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from models.database import db


class User(UserMixin, db.Model):
    """Registered student."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Simple, self-service password recovery (no mail server required).
    security_question = db.Column(db.String(255), default="")
    security_answer_hash = db.Column(db.String(255), default="")

    # Preferences
    theme = db.Column(db.String(10), default="dark")
    reminder_time = db.Column(db.String(5), default="19:00")

    # Gamification
    streak = db.Column(db.Integer, default=0)
    last_active_day = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Password helpers -------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def set_security_answer(self, answer: str) -> None:
        self.security_answer_hash = generate_password_hash(answer.strip().lower())

    def check_security_answer(self, answer: str) -> bool:
        if not self.security_answer_hash:
            return False
        return check_password_hash(self.security_answer_hash, answer.strip().lower())

    # --- Streak -----------------------------------------------------------
    def touch_streak(self) -> None:
        """Increment the streak once per calendar day of activity."""
        today = date.today()
        if self.last_active_day == today:
            return
        if self.last_active_day and (today - self.last_active_day).days == 1:
            self.streak = (self.streak or 0) + 1
        else:
            self.streak = 1
        self.last_active_day = today

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "theme": self.theme,
            "reminder_time": self.reminder_time,
            "streak": self.streak or 0,
        }
