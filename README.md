# StudyPilot — AI Smart Study Planner & Study Analyzer

A production-ready Flask application that turns an exam timetable and syllabus into a
personalised, adaptive study plan — with AI-generated MCQ tests, weak-topic analysis and
performance dashboards.

**Stack:** HTML5 · CSS3 · Vanilla JavaScript · Flask · SQLite · Groq (no React, no Bootstrap).

---

## Features

- Animated gradient landing page with glassmorphism cards, dark/light mode, fully responsive
- Register / login / forgot-password (security-question reset)
- Dashboard: greeting, exam countdown, progress ring, today's tasks, revision, streak,
  productivity score, completion %, AI suggestions, Pomodoro timer
- 5-step setup: timetable upload (PDF/image/manual) → unavailable days → daily availability →
  syllabus upload → plan generation
- Planner: monthly colour-coded calendar, drag-and-drop task moving, delete, regenerate one
  day or the whole timetable, PDF export
- AI MCQ generator (20 questions, 4 options, difficulty mix, explanations)
- Exam interface: timer, question palette, previous/next, progress bar, auto-submit
- AI analysis: weak/strong topics, concept gaps, time management, guessing pattern, confidence
- Performance dashboard with Chart.js (weekly, monthly, subject, chapter, accuracy, weak areas)
- Adaptive planner: low scores add revision, high scores add advanced practice
- Browser notification reminders (study, revision, mock, water, sleep)
- Exports: timetable PDF, performance PDF, study report PDF, JSON data dump

---

## Installation

```bash
cd study-planner
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optional (only needed to OCR **image** uploads — PDFs work without it):

- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`
- Windows: install from https://github.com/UB-Mannheim/tesseract/wiki

## Adding your Groq API key

1. Create a free key at https://console.groq.com/keys
2. Copy the example env file and paste your key:

```bash
cp .env.example .env
```

```env
GROQ_API_KEY=YOUR_API_KEY
GROQ_MODEL=llama-3.3-70b-versatile
SECRET_KEY=some-long-random-string
```

The app runs **without** a key: planning, timers, tests (template questions), charts and PDF
exports all work offline. The key unlocks AI document parsing, real MCQ generation, study
suggestions, motivation and deep analysis.

## Running

```bash
python app.py
```

Open http://127.0.0.1:5000 — `database.db` is created automatically on first run.

---

## Project structure

```
study-planner/
├── app.py                  # Routes / controllers
├── config.py               # Configuration
├── report_generator.py     # PDF reports (ReportLab)
├── requirements.txt
├── database.db             # Created on first run
├── models/                 # SQLAlchemy models
│   ├── database.py  user.py  study.py  test.py
├── services/               # Business logic
│   ├── planner.py  scheduler.py  groq_service.py  test_generator.py  analyzer.py
├── utils/                  # Helpers
│   ├── ocr.py  pdf_parser.py  parsers.py  date_utils.py
├── templates/              # Jinja views
└── static/
    ├── css/  js/  images/  uploads/
```

## API reference

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/upload-timetable` | Parse a PDF/image or accept manual exam rows |
| POST | `/upload-syllabus` | Parse a PDF/image or accept manual chapters |
| POST | `/generate-plan` | Build the full timetable |
| GET | `/api/planner` | Tasks grouped by day (optional `?month=YYYY-MM`) |
| POST | `/mark-complete` | Complete a task / chapter |
| POST | `/generate-test` | Generate an MCQ test for a chapter |
| POST | `/submit-test` | Grade a test and adapt the plan |
| GET | `/api/analysis` | AI analysis of the latest (or a given) test |
| GET | `/api/performance` | Chart aggregates |
| POST | `/update-plan` | Regenerate a single day |

Supporting endpoints: `/api/dashboard`, `/api/suggestions`, `/api/exams`, `/api/unavailable`,
`/api/availability`, `/api/syllabus`, `/api/tasks/<id>`, `/api/session`, `/api/timer-stats`,
`/api/reminders`, `/api/settings`, `/api/reset-planner`, `/api/export-data`,
`/export/timetable.pdf`, `/export/performance.pdf`, `/export/study-report.pdf`.

## Database tables

`users`, `subjects`, `chapters`, `exams`, `timetable`, `study_sessions`, `unavailable_days`,
`availability`, `tests`, `questions`, `answers`, `scores`, `performance`, `weak_topics`,
`reminders`.

## Screenshots

Add your own captures here:

| Landing | Dashboard | Planner | Test | Analysis |
| --- | --- | --- | --- | --- |
| `static/images/landing.png` | `static/images/dashboard.png` | `static/images/planner.png` | `static/images/test.png` | `static/images/analysis.png` |

## Future improvements

- Email/push reminders via a background APScheduler worker
- Spaced-repetition (SM-2) scheduling for revision blocks
- Collaborative study groups and shared plans
- Handwriting-aware OCR for scanned notes
- PostgreSQL + Docker deployment profile
