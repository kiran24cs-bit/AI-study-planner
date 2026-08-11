"""AI Smart Study Planner & Study Analyzer — Flask application entry point.

MVC layout:
  models/    -> SQLAlchemy models (M)
  templates/ -> Jinja templates (V)
  app.py     -> routes / controllers (C)
  services/  -> business logic (planner, AI, grading)
  utils/     -> pure helpers (parsing, dates, OCR)
"""

import os
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.utils import secure_filename

import config
import report_generator
from config import Config
from models.database import db, init_db
from models.study import (
    Availability,
    Chapter,
    Exam,
    Reminder,
    StudySession,
    Subject,
    TimetableTask,
    UnavailableDay,
    WeakTopic,
)
from models.test import Answer, Performance, Question, Score, Test
from models.user import User
from services import analyzer, groq_service, planner, test_generator
from utils import parsers
from utils.date_utils import parse_date, parse_time
from utils.ocr import extract_text_from_upload

# --------------------------------------------------------------------------
# App factory
# --------------------------------------------------------------------------

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    config.init_app(app)
    init_db(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_routes(app)
    return app


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def save_upload(file_storage):
    """Persist an upload and return its absolute path, or None if invalid."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_file(file_storage.filename):
        return None
    name = secure_filename(file_storage.filename)
    stamped = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{name}"
    path = os.path.join(Config.UPLOAD_FOLDER, stamped)
    file_storage.save(path)
    return path


def get_or_create_subject(user_id: int, name: str) -> Subject:
    """Look up a subject by name (case-insensitive) or create it."""
    name = (name or "Subject").strip()[:150]
    subject = Subject.query.filter(
        Subject.user_id == user_id, db.func.lower(Subject.name) == name.lower()
    ).first()
    if not subject:
        palette = ["#6366f1", "#06b6d4", "#f59e0b", "#ec4899", "#22c55e", "#ef4444"]
        count = Subject.query.filter_by(user_id=user_id).count()
        subject = Subject(user_id=user_id, name=name, color=palette[count % len(palette)])
        db.session.add(subject)
        db.session.commit()
    return subject


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

def register_routes(app):  # noqa: C901 - route table is intentionally flat

    # ---------------- Public ----------------
    @app.route("/")
    def index():
        return render_template("index.html")

    # ---------------- Auth ----------------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            question = (request.form.get("security_question") or "").strip()
            answer = (request.form.get("security_answer") or "").strip()

            if not name or not email or len(password) < 6:
                flash("Name, email and a 6+ character password are required.", "error")
                return render_template("register.html")
            if User.query.filter_by(email=email).first():
                flash("That email is already registered.", "error")
                return render_template("register.html")

            user = User(name=name, email=email, security_question=question)
            user.set_password(password)
            if answer:
                user.set_security_answer(answer)
            db.session.add(user)
            db.session.commit()

            db.session.add(Availability(user_id=user.id))
            db.session.commit()

            login_user(user)
            return redirect(url_for("dashboard"))
        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            password = request.form.get("password") or ""
            user = User.query.filter_by(email=email).first()
            if not user or not user.check_password(password):
                flash("Invalid email or password.", "error")
                return render_template("login.html")
            user.touch_streak()
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        stage = "email"
        user = None
        if request.method == "POST":
            email = (request.form.get("email") or "").strip().lower()
            user = User.query.filter_by(email=email).first()
            if not user:
                flash("No account found with that email.", "error")
                return render_template("login.html", forgot=True, stage="email")

            answer = request.form.get("security_answer")
            new_password = request.form.get("new_password")
            if answer is None:
                return render_template("login.html", forgot=True, stage="answer", user=user)

            if not user.check_security_answer(answer or ""):
                flash("Security answer did not match.", "error")
                return render_template("login.html", forgot=True, stage="answer", user=user)
            if not new_password or len(new_password) < 6:
                flash("New password must be at least 6 characters.", "error")
                return render_template("login.html", forgot=True, stage="answer", user=user)

            user.set_password(new_password)
            db.session.commit()
            flash("Password updated. Please sign in.", "success")
            return redirect(url_for("login"))
        return render_template("login.html", forgot=True, stage=stage)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    # ---------------- Dashboard ----------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        current_user.touch_streak()
        db.session.commit()
        return render_template("dashboard.html", user=current_user)

    @app.route("/api/dashboard")
    @login_required
    def api_dashboard():
        """Everything the dashboard widgets need, in one payload."""
        uid = current_user.id
        today = date.today()

        exams = Exam.query.filter(Exam.user_id == uid, Exam.exam_date >= today).order_by(
            Exam.exam_date
        ).all()
        today_tasks = (
            TimetableTask.query.filter_by(user_id=uid, day=today)
            .order_by(TimetableTask.start_time)
            .all()
        )
        all_tasks = TimetableTask.query.filter_by(user_id=uid).all()
        done = sum(1 for t in all_tasks if t.status == "completed")
        completion = round(done / len(all_tasks) * 100, 1) if all_tasks else 0.0

        minutes_today = sum(
            s.minutes
            for s in StudySession.query.filter(
                StudySession.user_id == uid,
                StudySession.created_at >= datetime.combine(today, datetime.min.time()),
            ).all()
        )
        recent = (
            Score.query.filter_by(user_id=uid).order_by(Score.created_at.desc()).limit(5).all()
        )
        avg_score = round(sum(s.percentage for s in recent) / len(recent), 1) if recent else 0.0

        # Productivity = 60% plan adherence + 40% recent test performance.
        productivity = round(completion * 0.6 + avg_score * 0.4, 1)

        countdown = None
        if exams:
            countdown = {
                "subject": exams[0].subject_name,
                "date": exams[0].exam_date.isoformat(),
                "days": (exams[0].exam_date - today).days,
            }

        return jsonify(
            {
                "user": current_user.to_dict(),
                "countdown": countdown,
                "today_tasks": [t.to_dict() for t in today_tasks],
                "revision_today": [
                    t.to_dict() for t in today_tasks if t.task_type in ("revision", "final")
                ],
                "upcoming_exams": [e.to_dict() for e in exams[:5]],
                "completion": completion,
                "productivity": productivity,
                "streak": current_user.streak or 0,
                "minutes_today": minutes_today,
                "avg_score": avg_score,
                "weak_topics": [
                    w.to_dict() for w in WeakTopic.query.filter_by(user_id=uid).limit(6).all()
                ],
            }
        )

    @app.route("/api/suggestions")
    @login_required
    def api_suggestions():
        """AI suggestions + a motivational line (cached per session for speed)."""
        uid = current_user.id
        pending = TimetableTask.query.filter_by(user_id=uid, status="pending").count()
        weak = [w.topic for w in WeakTopic.query.filter_by(user_id=uid).limit(5).all()]
        next_exam = (
            Exam.query.filter(Exam.user_id == uid, Exam.exam_date >= date.today())
            .order_by(Exam.exam_date)
            .first()
        )
        context = (
            f"Pending tasks: {pending}. Weak topics: {', '.join(weak) or 'none'}. "
            f"Next exam: {next_exam.subject_name if next_exam else 'none'} "
            f"on {next_exam.exam_date if next_exam else '-'}. Streak: {current_user.streak}."
        )
        return jsonify(
            {
                "suggestions": groq_service.study_suggestions(context),
                "motivation": groq_service.daily_motivation(),
                "ai_enabled": groq_service.is_configured(),
            }
        )

    # ---------------- Step 1: timetable ----------------
    @app.route("/onboarding")
    @login_required
    def onboarding():
        return render_template("onboarding.html", user=current_user)

    @app.route("/upload-timetable", methods=["POST"])
    @login_required
    def upload_timetable():
        """Accept a PDF/image upload OR manual JSON rows."""
        uid = current_user.id
        rows = []

        if request.files.get("file"):
            path = save_upload(request.files["file"])
            if not path:
                return jsonify({"ok": False, "error": "Unsupported file type."}), 400
            text = extract_text_from_upload(path)
            if not text.strip():
                return jsonify(
                    {
                        "ok": False,
                        "error": "Could not read the file. Install Tesseract for images, "
                        "or use manual entry.",
                    }
                ), 422
            parsed = groq_service.parse_timetable(text)
            rows = parsed.get("exams", []) if isinstance(parsed, dict) else []
            if not rows:
                rows = parsers.heuristic_exams(text)
        else:
            payload = request.get_json(silent=True) or {}
            rows = payload.get("exams", [])

        created = 0
        for row in rows:
            exam_date = parse_date(row.get("date"))
            subject_name = (row.get("subject") or "").strip()
            if not exam_date or not subject_name:
                continue
            subject = get_or_create_subject(uid, subject_name)
            db.session.add(
                Exam(
                    user_id=uid,
                    subject_id=subject.id,
                    subject_name=subject.name,
                    exam_date=exam_date,
                    exam_time=parse_time(row.get("time"), "09:00"),
                    duration_minutes=int(row.get("duration_minutes") or 180),
                )
            )
            created += 1
        db.session.commit()

        if not created:
            return jsonify({"ok": False, "error": "No valid exam rows found."}), 422
        return jsonify({"ok": True, "created": created, "exams": _exams_json(uid)})

    @app.route("/api/exams")
    @login_required
    def api_exams():
        return jsonify({"exams": _exams_json(current_user.id)})

    @app.route("/api/exams/<int:exam_id>", methods=["DELETE"])
    @login_required
    def delete_exam(exam_id):
        exam = Exam.query.filter_by(id=exam_id, user_id=current_user.id).first_or_404()
        db.session.delete(exam)
        db.session.commit()
        return jsonify({"ok": True})

    def _exams_json(uid):
        return [
            e.to_dict()
            for e in Exam.query.filter_by(user_id=uid).order_by(Exam.exam_date).all()
        ]

    # ---------------- Step 2: unavailable days ----------------
    @app.route("/api/unavailable", methods=["GET", "POST"])
    @login_required
    def api_unavailable():
        uid = current_user.id
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            day = parse_date(payload.get("day"))
            if not day:
                return jsonify({"ok": False, "error": "Invalid date."}), 400
            if not UnavailableDay.query.filter_by(user_id=uid, day=day).first():
                db.session.add(
                    UnavailableDay(
                        user_id=uid,
                        day=day,
                        reason=(payload.get("reason") or "Unavailable")[:120],
                    )
                )
                db.session.commit()
        days = UnavailableDay.query.filter_by(user_id=uid).order_by(UnavailableDay.day).all()
        return jsonify({"ok": True, "days": [d.to_dict() for d in days]})

    @app.route("/api/unavailable/<int:day_id>", methods=["DELETE"])
    @login_required
    def delete_unavailable(day_id):
        row = UnavailableDay.query.filter_by(id=day_id, user_id=current_user.id).first_or_404()
        db.session.delete(row)
        db.session.commit()
        return jsonify({"ok": True})

    # ---------------- Step 3: availability ----------------
    @app.route("/api/availability", methods=["GET", "POST"])
    @login_required
    def api_availability():
        availability = planner.get_availability(current_user.id)
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            time_fields = [
                "wake_time",
                "sleep_time",
                "college_start",
                "college_end",
                "work_start",
                "work_end",
                "break_start",
                "break_end",
                "preferred_start",
            ]
            for field in time_fields:
                if field in payload:
                    value = payload.get(field) or ""
                    setattr(availability, field, parse_time(value, "") if value else "")
            if "max_daily_hours" in payload:
                availability.max_daily_hours = max(
                    1.0, min(float(payload.get("max_daily_hours") or 6), 16.0)
                )
            if "session_minutes" in payload:
                availability.session_minutes = max(
                    20, min(int(payload.get("session_minutes") or 60), 180)
                )
            db.session.commit()
        return jsonify({"ok": True, "availability": availability.to_dict()})

    # ---------------- Step 4: syllabus ----------------
    @app.route("/upload-syllabus", methods=["POST"])
    @login_required
    def upload_syllabus():
        uid = current_user.id
        subjects_payload = []

        if request.files.get("file"):
            path = save_upload(request.files["file"])
            if not path:
                return jsonify({"ok": False, "error": "Unsupported file type."}), 400
            text = extract_text_from_upload(path)
            if not text.strip():
                return jsonify({"ok": False, "error": "Could not read the file."}), 422
            parsed = groq_service.parse_syllabus(text)
            subjects_payload = parsed.get("subjects", []) if isinstance(parsed, dict) else []
            if not subjects_payload:
                subjects_payload = parsers.heuristic_syllabus(text)
        else:
            payload = request.get_json(silent=True) or {}
            subjects_payload = payload.get("subjects", [])

        created = 0
        for item in subjects_payload:
            subject = get_or_create_subject(uid, item.get("name"))
            for chapter in item.get("chapters", []):
                name = (chapter.get("name") or "").strip()
                if not name:
                    continue
                db.session.add(
                    Chapter(
                        subject_id=subject.id,
                        unit=(chapter.get("unit") or "")[:150],
                        name=name[:200],
                        topics=(chapter.get("topics") or "")[:2000],
                        difficulty=_clamp_int(chapter.get("difficulty"), 1, 5, 3),
                        estimated_hours=max(0.5, float(chapter.get("estimated_hours") or 2.0)),
                        priority=_clamp_int(chapter.get("priority"), 1, 5, 3),
                    )
                )
                created += 1
        db.session.commit()

        if not created:
            return jsonify({"ok": False, "error": "No chapters found."}), 422
        return jsonify({"ok": True, "created": created, "subjects": _syllabus_json(uid)})

    @app.route("/api/syllabus")
    @login_required
    def api_syllabus():
        return jsonify({"subjects": _syllabus_json(current_user.id)})

    @app.route("/api/chapters/<int:chapter_id>", methods=["DELETE"])
    @login_required
    def delete_chapter(chapter_id):
        chapter = (
            Chapter.query.join(Subject)
            .filter(Chapter.id == chapter_id, Subject.user_id == current_user.id)
            .first_or_404()
        )
        db.session.delete(chapter)
        db.session.commit()
        return jsonify({"ok": True})

    def _syllabus_json(uid):
        out = []
        for subject in Subject.query.filter_by(user_id=uid).order_by(Subject.name).all():
            out.append(
                {
                    **subject.to_dict(),
                    "chapters": [c.to_dict() for c in subject.chapters.all()],
                }
            )
        return out

    def _clamp_int(value, low, high, default):
        try:
            return max(low, min(int(value), high))
        except (TypeError, ValueError):
            return default

    # ---------------- Step 5: planner ----------------
    @app.route("/planner")
    @login_required
    def planner_page():
        return render_template("planner.html", user=current_user)

    @app.route("/generate-plan", methods=["POST"])
    @login_required
    def generate_plan():
        result = planner.generate_plan(current_user.id)
        ok = result["tasks"] > 0
        return jsonify({"ok": ok, **result}), (200 if ok else 422)

    @app.route("/update-plan", methods=["POST"])
    @login_required
    def update_plan():
        """Regenerate a single day (pass {"day": "YYYY-MM-DD"})."""
        payload = request.get_json(silent=True) or {}
        day = parse_date(payload.get("day")) or date.today()
        result = planner.regenerate_day(current_user.id, day)
        return jsonify({"ok": True, **result})

    @app.route("/api/planner")
    @login_required
    def api_planner():
        """Tasks grouped by day, optionally filtered by month (?month=YYYY-MM)."""
        uid = current_user.id
        query = TimetableTask.query.filter_by(user_id=uid)
        month = request.args.get("month")
        if month:
            try:
                year, mon = (int(p) for p in month.split("-"))
                start = date(year, mon, 1)
                end = date(year + (mon == 12), (mon % 12) + 1, 1) - timedelta(days=1)
                query = query.filter(TimetableTask.day >= start, TimetableTask.day <= end)
            except (ValueError, TypeError):
                pass

        tasks = query.order_by(
            TimetableTask.day, TimetableTask.position, TimetableTask.start_time
        ).all()
        grouped = {}
        for task in tasks:
            grouped.setdefault(task.day.isoformat(), []).append(task.to_dict())

        exams = {
            e.exam_date.isoformat(): e.subject_name
            for e in Exam.query.filter_by(user_id=uid).all()
        }
        blocked = {
            d.day.isoformat(): d.reason
            for d in UnavailableDay.query.filter_by(user_id=uid).all()
        }
        return jsonify({"days": grouped, "exams": exams, "unavailable": blocked})

    @app.route("/api/tasks/<int:task_id>", methods=["PATCH", "DELETE"])
    @login_required
    def api_task(task_id):
        task = TimetableTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
        if request.method == "DELETE":
            db.session.delete(task)
            db.session.commit()
            return jsonify({"ok": True})

        payload = request.get_json(silent=True) or {}
        if "day" in payload:
            new_day = parse_date(payload["day"])
            if new_day:
                task.day = new_day
        if "start_time" in payload:
            task.start_time = parse_time(payload["start_time"], task.start_time)
        if "position" in payload:
            task.position = _clamp_int(payload["position"], 0, 999, task.position)
        if "status" in payload and payload["status"] in ("pending", "completed"):
            task.status = payload["status"]
        db.session.commit()
        return jsonify({"ok": True, "task": task.to_dict()})

    @app.route("/mark-complete", methods=["POST"])
    @login_required
    def mark_complete():
        """Mark a task (and optionally its chapter) as complete."""
        payload = request.get_json(silent=True) or {}
        uid = current_user.id
        task = TimetableTask.query.filter_by(id=payload.get("task_id"), user_id=uid).first()
        if not task:
            return jsonify({"ok": False, "error": "Task not found."}), 404

        task.status = "completed"
        current_user.touch_streak()

        today = date.today()
        row = Performance.query.filter_by(user_id=uid, day=today).first()
        if not row:
            row = Performance(user_id=uid, day=today)
            db.session.add(row)
        row.tasks_completed = (row.tasks_completed or 0) + 1
        row.study_minutes = (row.study_minutes or 0) + task.duration_minutes

        chapter_completed = False
        if payload.get("complete_chapter") and task.chapter_id:
            chapter = db.session.get(Chapter, task.chapter_id)
            if chapter:
                chapter.completed = True
                chapter.completed_at = datetime.utcnow()
                chapter_completed = True
        db.session.commit()

        return jsonify(
            {
                "ok": True,
                "chapter_completed": chapter_completed,
                "chapter_id": task.chapter_id,
                "offer_test": chapter_completed,
            }
        )

    @app.route("/api/chapters/<int:chapter_id>/complete", methods=["POST"])
    @login_required
    def complete_chapter(chapter_id):
        chapter = (
            Chapter.query.join(Subject)
            .filter(Chapter.id == chapter_id, Subject.user_id == current_user.id)
            .first_or_404()
        )
        chapter.completed = True
        chapter.completed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"ok": True, "offer_test": True, "chapter_id": chapter.id})

    # ---------------- Tests ----------------
    @app.route("/generate-test", methods=["POST"])
    @login_required
    def generate_test():
        payload = request.get_json(silent=True) or {}
        chapter = (
            Chapter.query.join(Subject)
            .filter(Chapter.id == payload.get("chapter_id"), Subject.user_id == current_user.id)
            .first()
        )
        if not chapter:
            return jsonify({"ok": False, "error": "Chapter not found."}), 404
        count = _clamp_int(payload.get("count"), 5, 30, 20)
        test = test_generator.create_test(current_user.id, chapter, count)
        return jsonify({"ok": True, "test_id": test.id, "url": url_for("test_page", test_id=test.id)})

    @app.route("/test/<int:test_id>")
    @login_required
    def test_page(test_id):
        test = Test.query.filter_by(id=test_id, user_id=current_user.id).first_or_404()
        return render_template("test.html", user=current_user, test=test)

    @app.route("/api/test/<int:test_id>")
    @login_required
    def api_test(test_id):
        test = Test.query.filter_by(id=test_id, user_id=current_user.id).first_or_404()
        return jsonify(test.to_dict(include_answers=False))

    @app.route("/submit-test", methods=["POST"])
    @login_required
    def submit_test():
        payload = request.get_json(silent=True) or {}
        test = Test.query.filter_by(id=payload.get("test_id"), user_id=current_user.id).first()
        if not test:
            return jsonify({"ok": False, "error": "Test not found."}), 404

        score = analyzer.grade_test(
            current_user.id, test, payload.get("answers") or {}, payload.get("timings") or {}
        )
        adaptation = planner.adapt_after_test(current_user.id, score)
        return jsonify(
            {
                "ok": True,
                "score": score.to_dict(),
                "adaptation": adaptation,
                "analysis_url": url_for("analysis_page", test_id=test.id),
            }
        )

    # ---------------- Analysis & performance ----------------
    @app.route("/analysis")
    @app.route("/analysis/<int:test_id>")
    @login_required
    def analysis_page(test_id=None):
        return render_template("analysis.html", user=current_user, test_id=test_id)

    @app.route("/api/analysis")
    @app.route("/api/analysis/<int:test_id>")
    @login_required
    def api_analysis(test_id=None):
        uid = current_user.id
        if test_id:
            test = Test.query.filter_by(id=test_id, user_id=uid).first_or_404()
            score = Score.query.filter_by(test_id=test.id, user_id=uid).first()
        else:
            score = Score.query.filter_by(user_id=uid).order_by(Score.created_at.desc()).first()
            test = db.session.get(Test, score.test_id) if score else None

        if not score or not test:
            return jsonify({"ok": False, "error": "No test results yet."}), 404
        return jsonify({"ok": True, "analysis": analyzer.build_analysis(uid, test, score)})

    @app.route("/performance")
    @login_required
    def performance_page():
        return render_template("performance.html", user=current_user)

    @app.route("/api/performance")
    @login_required
    def api_performance():
        """Aggregates for every Chart.js chart on the performance page."""
        uid = current_user.id
        today = date.today()
        scores = Score.query.filter_by(user_id=uid).order_by(Score.created_at).all()

        weekly = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            row = Performance.query.filter_by(user_id=uid, day=day).first()
            weekly.append(
                {
                    "day": day.strftime("%a"),
                    "minutes": row.study_minutes if row else 0,
                    "tasks": row.tasks_completed if row else 0,
                    "score": round(row.avg_score, 1) if row else 0,
                }
            )

        monthly = []
        for offset in range(29, -1, -1):
            day = today - timedelta(days=offset)
            row = Performance.query.filter_by(user_id=uid, day=day).first()
            monthly.append({"day": day.strftime("%d %b"), "minutes": row.study_minutes if row else 0})

        by_subject = {}
        by_chapter = {}
        for score in scores:
            by_subject.setdefault(score.subject_name, []).append(score.percentage)
            by_chapter.setdefault(score.chapter_name, []).append(score.percentage)

        return jsonify(
            {
                "weekly": weekly,
                "monthly": monthly,
                "subjects": [
                    {"name": k, "avg": round(sum(v) / len(v), 1)} for k, v in by_subject.items()
                ],
                "chapters": [
                    {"name": k, "avg": round(sum(v) / len(v), 1)} for k, v in by_chapter.items()
                ],
                "accuracy": [
                    {"date": s.created_at.strftime("%d %b"), "value": round(s.accuracy, 1)}
                    for s in scores
                ],
                "weak_topics": [
                    w.to_dict() for w in WeakTopic.query.filter_by(user_id=uid).all()
                ],
                "history": [s.to_dict() for s in scores],
            }
        )

    # ---------------- Timer, reminders, settings ----------------
    @app.route("/api/session", methods=["POST"])
    @login_required
    def api_session():
        payload = request.get_json(silent=True) or {}
        minutes = _clamp_int(payload.get("minutes"), 1, 240, 25)
        db.session.add(
            StudySession(
                user_id=current_user.id,
                minutes=minutes,
                mode=(payload.get("mode") or "pomodoro")[:20],
            )
        )
        row = Performance.query.filter_by(user_id=current_user.id, day=date.today()).first()
        if not row:
            row = Performance(user_id=current_user.id, day=date.today())
            db.session.add(row)
        row.study_minutes = (row.study_minutes or 0) + minutes
        current_user.touch_streak()
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/timer-stats")
    @login_required
    def api_timer_stats():
        uid = current_user.id
        sessions = StudySession.query.filter_by(user_id=uid).all()
        today_start = datetime.combine(date.today(), datetime.min.time())
        return jsonify(
            {
                "total_sessions": len(sessions),
                "total_minutes": sum(s.minutes for s in sessions),
                "today_minutes": sum(
                    s.minutes for s in sessions if s.created_at >= today_start
                ),
            }
        )

    @app.route("/api/reminders", methods=["GET", "POST"])
    @login_required
    def api_reminders():
        uid = current_user.id
        if request.method == "POST":
            payload = request.get_json(silent=True) or {}
            kind = (payload.get("kind") or "study")[:30]
            reminder = Reminder.query.filter_by(user_id=uid, kind=kind).first()
            if not reminder:
                reminder = Reminder(user_id=uid, kind=kind)
                db.session.add(reminder)
            reminder.time = parse_time(payload.get("time"), reminder.time or "19:00")
            reminder.enabled = bool(payload.get("enabled", True))
            db.session.commit()
        return jsonify(
            {"reminders": [r.to_dict() for r in Reminder.query.filter_by(user_id=uid).all()]}
        )

    @app.route("/settings")
    @login_required
    def settings_page():
        return render_template("settings.html", user=current_user)

    @app.route("/api/settings", methods=["POST"])
    @login_required
    def api_settings():
        payload = request.get_json(silent=True) or {}
        if payload.get("theme") in ("dark", "light"):
            current_user.theme = payload["theme"]
        if payload.get("reminder_time"):
            current_user.reminder_time = parse_time(payload["reminder_time"], "19:00")
        db.session.commit()
        return jsonify({"ok": True, "user": current_user.to_dict()})

    @app.route("/api/reset-planner", methods=["POST"])
    @login_required
    def reset_planner():
        TimetableTask.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({"ok": True, "message": "Planner cleared."})

    @app.route("/api/export-data")
    @login_required
    def export_data():
        """Full JSON dump of the account (GDPR-style export)."""
        uid = current_user.id
        return jsonify(
            {
                "user": current_user.to_dict(),
                "exams": _exams_json(uid),
                "syllabus": _syllabus_json(uid),
                "unavailable": [
                    d.to_dict() for d in UnavailableDay.query.filter_by(user_id=uid).all()
                ],
                "availability": planner.get_availability(uid).to_dict(),
                "timetable": [
                    t.to_dict() for t in TimetableTask.query.filter_by(user_id=uid).all()
                ],
                "scores": [s.to_dict() for s in Score.query.filter_by(user_id=uid).all()],
                "weak_topics": [
                    w.to_dict() for w in WeakTopic.query.filter_by(user_id=uid).all()
                ],
            }
        )

    # ---------------- PDF exports ----------------
    @app.route("/export/timetable.pdf")
    @login_required
    def export_timetable_pdf():
        tasks = (
            TimetableTask.query.filter_by(user_id=current_user.id)
            .order_by(TimetableTask.day, TimetableTask.start_time)
            .all()
        )
        buffer = report_generator.timetable_pdf(current_user, tasks)
        return send_file(buffer, mimetype="application/pdf", download_name="timetable.pdf")

    @app.route("/export/performance.pdf")
    @login_required
    def export_performance_pdf():
        scores = (
            Score.query.filter_by(user_id=current_user.id).order_by(Score.created_at).all()
        )
        buffer = report_generator.performance_pdf(current_user, scores)
        return send_file(buffer, mimetype="application/pdf", download_name="performance.pdf")

    @app.route("/export/study-report.pdf")
    @login_required
    def export_study_report_pdf():
        uid = current_user.id
        tasks = TimetableTask.query.filter_by(user_id=uid).all()
        done = sum(1 for t in tasks if t.status == "completed")
        scores = Score.query.filter_by(user_id=uid).all()
        stats = {
            "Total tasks": len(tasks),
            "Completed tasks": done,
            "Completion %": round(done / len(tasks) * 100, 1) if tasks else 0,
            "Tests taken": len(scores),
            "Average score %": round(sum(s.percentage for s in scores) / len(scores), 1)
            if scores
            else 0,
            "Study streak (days)": current_user.streak or 0,
        }
        weak = WeakTopic.query.filter_by(user_id=uid).all()
        suggestions = groq_service.study_suggestions(
            f"Completion {stats['Completion %']}%, average score {stats['Average score %']}%, "
            f"weak topics: {', '.join(w.topic for w in weak) or 'none'}."
        )
        buffer = report_generator.study_report_pdf(current_user, stats, weak, suggestions)
        return send_file(buffer, mimetype="application/pdf", download_name="study-report.pdf")

    # ---------------- Errors ----------------
    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "Not found"}), 404
        return render_template("index.html"), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return jsonify({"ok": False, "error": "Internal server error"}), 500


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
