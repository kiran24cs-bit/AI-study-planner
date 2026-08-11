"""Application configuration.

All values can be overridden through environment variables (see .env.example).
"""

import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration shared by every environment."""

    # --- Core Flask -------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # --- Database ---------------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Uploads ----------------------------------------------------------
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB per request
    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "webp"}

    # --- AI (Groq) --------------------------------------------------------
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # --- Planner defaults -------------------------------------------------
    DEFAULT_SESSION_MINUTES = 60
    DEFAULT_MAX_DAILY_HOURS = 6
    BUFFER_DAYS_BEFORE_EXAM = 2  # reserved for final revision


def init_app(app):
    """Create runtime folders the app depends on."""
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
