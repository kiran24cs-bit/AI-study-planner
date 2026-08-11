"""Builds MCQ tests from a completed chapter using Groq (with offline fallback)."""

from models.database import db
from models.study import Chapter
from models.test import Question, Test
from services import groq_service

VALID_OPTIONS = {"A", "B", "C", "D"}


def _fallback_questions(chapter: Chapter, count: int):
    """Deterministic placeholder set so the flow works without an API key."""
    topics = [t.strip() for t in (chapter.topics or "").split(",") if t.strip()]
    if not topics:
        topics = [chapter.name]
    questions = []
    for index in range(count):
        topic = topics[index % len(topics)]
        questions.append(
            {
                "text": f"Q{index + 1}. Which statement best describes '{topic}'?",
                "options": {
                    "A": f"{topic} is a core concept of {chapter.name}.",
                    "B": f"{topic} is unrelated to {chapter.name}.",
                    "C": f"{topic} only applies outside {chapter.name}.",
                    "D": "None of the above.",
                },
                "correct": "A",
                "difficulty": ["easy", "medium", "hard"][index % 3],
                "explanation": f"'{topic}' is studied as part of {chapter.name}.",
                "topic": topic,
            }
        )
    return questions


def _normalise(raw, chapter):
    """Validate one AI question dict; return None when it is unusable."""
    if not isinstance(raw, dict):
        return None
    text = str(raw.get("text") or raw.get("question") or "").strip()
    options = raw.get("options") or {}
    if not text or not isinstance(options, dict):
        return None
    letters = {k.upper(): str(v) for k, v in options.items() if k.upper() in VALID_OPTIONS}
    if len(letters) != 4:
        return None
    correct = str(raw.get("correct") or raw.get("answer") or "A").strip().upper()[:1]
    if correct not in VALID_OPTIONS:
        correct = "A"
    difficulty = str(raw.get("difficulty", "medium")).lower()
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "medium"
    return {
        "text": text,
        "options": letters,
        "correct": correct,
        "difficulty": difficulty,
        "explanation": str(raw.get("explanation", "")),
        "topic": str(raw.get("topic") or chapter.name),
    }


def create_test(user_id: int, chapter: Chapter, count: int = 20) -> Test:
    """Generate and persist a new test for a chapter."""
    raw_questions = groq_service.generate_mcqs(
        chapter.subject.name, chapter.name, chapter.topics or "", count
    )
    cleaned = [q for q in (_normalise(r, chapter) for r in raw_questions) if q]
    if len(cleaned) < 5:
        cleaned = _fallback_questions(chapter, count)
    cleaned = cleaned[:count]

    test = Test(
        user_id=user_id,
        chapter_id=chapter.id,
        subject_name=chapter.subject.name,
        chapter_name=chapter.name,
        duration_minutes=max(10, len(cleaned)),
    )
    db.session.add(test)
    db.session.flush()  # assign test.id

    for item in cleaned:
        db.session.add(
            Question(
                test_id=test.id,
                text=item["text"],
                option_a=item["options"]["A"],
                option_b=item["options"]["B"],
                option_c=item["options"]["C"],
                option_d=item["options"]["D"],
                correct_option=item["correct"],
                difficulty=item["difficulty"],
                explanation=item["explanation"],
                topic=item["topic"],
            )
        )

    db.session.commit()
    return test
