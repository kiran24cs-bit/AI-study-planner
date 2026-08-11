"""Scores submitted tests and produces the AI study analysis."""

import json
from collections import defaultdict
from datetime import date

from models.database import db
from models.study import WeakTopic
from models.test import Answer, Performance, Question, Score, Test
from services import groq_service


def grade_test(user_id: int, test: Test, responses: dict, timings: dict) -> Score:
    """Persist answers and compute the aggregated score.

    `responses`: {question_id: "A"|"B"|"C"|"D"|None}
    `timings`:   {question_id: seconds spent}
    """
    questions = test.questions.all()
    correct = wrong = skipped = 0
    total_seconds = 0

    Answer.query.filter_by(test_id=test.id).delete()

    for question in questions:
        selected = (responses.get(str(question.id)) or responses.get(question.id) or "")
        selected = str(selected).strip().upper()[:1] or None
        seconds = int(timings.get(str(question.id), timings.get(question.id, 0)) or 0)
        total_seconds += seconds

        is_correct = selected == question.correct_option
        if selected is None:
            skipped += 1
        elif is_correct:
            correct += 1
        else:
            wrong += 1

        db.session.add(
            Answer(
                test_id=test.id,
                question_id=question.id,
                selected_option=selected,
                is_correct=bool(is_correct),
                seconds_spent=seconds,
            )
        )

    total = len(questions) or 1
    attempted = correct + wrong
    score = Score(
        user_id=user_id,
        test_id=test.id,
        subject_name=test.subject_name,
        chapter_name=test.chapter_name,
        total=total,
        correct=correct,
        wrong=wrong,
        skipped=skipped,
        percentage=round(correct / total * 100, 2),
        accuracy=round((correct / attempted * 100) if attempted else 0.0, 2),
        speed=round(total_seconds / total, 2),
    )
    test.submitted = True
    db.session.add(score)
    db.session.commit()

    _update_weak_topics(user_id, test, questions)
    _update_performance(user_id, score)
    return score


def _update_weak_topics(user_id, test, questions):
    """Recompute weak topics from the per-topic accuracy of this test."""
    stats = defaultdict(lambda: {"correct": 0, "total": 0})
    answers = {a.question_id: a for a in Answer.query.filter_by(test_id=test.id).all()}

    for question in questions:
        topic = question.topic or test.chapter_name
        stats[topic]["total"] += 1
        answer = answers.get(question.id)
        if answer and answer.is_correct:
            stats[topic]["correct"] += 1

    for topic, data in stats.items():
        accuracy = data["correct"] / data["total"] * 100
        existing = WeakTopic.query.filter_by(user_id=user_id, topic=topic).first()
        if accuracy < 60:
            if existing:
                existing.score = accuracy
            else:
                db.session.add(
                    WeakTopic(
                        user_id=user_id,
                        subject_name=test.subject_name,
                        topic=topic,
                        score=accuracy,
                    )
                )
        elif existing:
            db.session.delete(existing)
    db.session.commit()


def _update_performance(user_id, score):
    """Roll the score into today's performance record."""
    today = date.today()
    row = Performance.query.filter_by(user_id=user_id, day=today).first()
    if not row:
        row = Performance(user_id=user_id, day=today)
        db.session.add(row)
    previous = row.avg_score or 0.0
    row.avg_score = score.percentage if previous == 0 else (previous + score.percentage) / 2
    db.session.commit()


def build_analysis(user_id: int, test: Test, score: Score) -> dict:
    """Detailed AI report for a submitted test."""
    answers = {a.question_id: a for a in Answer.query.filter_by(test_id=test.id).all()}
    mistakes = []
    for question in test.questions.all():
        answer = answers.get(question.id)
        if answer and not answer.is_correct:
            mistakes.append(
                {
                    "topic": question.topic,
                    "difficulty": question.difficulty,
                    "chosen": answer.selected_option,
                    "correct": question.correct_option,
                    "seconds": answer.seconds_spent,
                }
            )

    payload = json.dumps(
        {
            "subject": test.subject_name,
            "chapter": test.chapter_name,
            "percentage": score.percentage,
            "accuracy": score.accuracy,
            "avg_seconds_per_question": score.speed,
            "skipped": score.skipped,
            "mistakes": mistakes[:25],
        }
    )

    report = groq_service.analyze_performance(payload)
    report.setdefault("weak_topics", sorted({m["topic"] for m in mistakes}))
    report.setdefault("strong_topics", [])
    report["score"] = score.to_dict()
    report["mistakes"] = mistakes
    return report
