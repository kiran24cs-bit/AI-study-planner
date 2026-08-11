"""Single SQLAlchemy instance shared by every model module."""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app):
    """Bind SQLAlchemy to the Flask app and create missing tables."""
    db.init_app(app)
    with app.app_context():
        # Importing the model modules registers their tables on the metadata.
        from models import user, study, test  # noqa: F401

        db.create_all()
