"""Thin, defensive wrapper around the Groq chat completions API.

Every public helper degrades gracefully: when no API key is configured (or the
network call fails) it returns a deterministic offline fallback so the app
remains fully usable without AI.
"""

import json
import re

from config import Config


def is_configured() -> bool:
    """True when a Groq API key is present."""
    return bool(Config.GROQ_API_KEY)


def _client():
    from groq import Groq

    return Groq(api_key=Config.GROQ_API_KEY)


def chat(prompt: str, system: str = "You are a helpful study coach.", json_mode=False):
    """Send a single-turn prompt to Groq. Returns text, or None on failure."""
    if not is_configured():
        return None
    try:
        kwargs = {
            "model": Config.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.6,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = _client().chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as exc:  # network / quota / model errors
        print(f"[groq_service] request failed: {exc}")
        return None


def chat_json(prompt: str, system: str, fallback):
    """Ask Groq for JSON and parse it. Returns `fallback` on any problem."""
    raw = chat(prompt, system=system, json_mode=True)
    if not raw:
        return fallback
    parsed = _loads(raw)
    return parsed if parsed is not None else fallback


def _loads(raw: str):
    """Parse JSON, tolerating markdown fences and trailing prose."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"[\[{].*[\]}]", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# --------------------------------------------------------------------------
# Domain-specific prompts
# --------------------------------------------------------------------------

def parse_timetable(text: str):
    """Extract exam rows from raw OCR/PDF text."""
    fallback = {"exams": []}
    if not text.strip():
        return fallback
    prompt = (
        "Extract the exam timetable from the text below.\n"
        'Return JSON: {"exams":[{"subject":"","date":"YYYY-MM-DD",'
        '"time":"HH:MM","duration_minutes":180}]}\n'
        "Only include rows you are confident about.\n\nTEXT:\n" + text[:6000]
    )
    return chat_json(prompt, "You extract structured data from documents.", fallback)


def parse_syllabus(text: str):
    """Extract a syllabus tree from raw OCR/PDF text."""
    fallback = {"subjects": []}
    if not text.strip():
        return fallback
    prompt = (
        "Extract the syllabus from the text below.\n"
        'Return JSON: {"subjects":[{"name":"","chapters":[{"unit":"","name":"",'
        '"topics":"comma separated","difficulty":1-5,"estimated_hours":2.0,'
        '"priority":1-5}]}]}\n\nTEXT:\n' + text[:6000]
    )
    return chat_json(prompt, "You extract structured data from documents.", fallback)


def generate_mcqs(subject: str, chapter: str, topics: str, count: int = 20):
    """Generate MCQs for a completed chapter."""
    prompt = (
        f"Create {count} multiple choice questions for the chapter "
        f'"{chapter}" of the subject "{subject}". Topics: {topics or chapter}.\n'
        "Mix difficulty: roughly 40% easy, 40% medium, 20% hard.\n"
        'Return JSON: {"questions":[{"text":"","options":{"A":"","B":"","C":"","D":""},'
        '"correct":"A","difficulty":"easy|medium|hard","explanation":"","topic":""}]}'
    )
    result = chat_json(prompt, "You are an exam question writer.", {"questions": []})
    return result.get("questions", []) if isinstance(result, dict) else []


def study_suggestions(context: str):
    """Short, actionable suggestions for the dashboard."""
    fallback = [
        "Start with your hardest subject while your focus is freshest.",
        "Revise yesterday's chapter for 15 minutes before new material.",
        "Take a 5 minute break after every focus session.",
    ]
    result = chat_json(
        "Give 3 short actionable study suggestions based on this context.\n"
        'Return JSON: {"suggestions":["...","...","..."]}\n\n' + context,
        "You are a concise study coach.",
        {"suggestions": fallback},
    )
    return result.get("suggestions", fallback)[:3]


def daily_motivation():
    """One motivational line."""
    text = chat("Give one short motivational line for a student. Max 15 words.")
    return (text or "Small consistent steps beat last-minute panic. Keep going.").strip().strip('"')


def analyze_performance(payload: str):
    """Deep analysis of a submitted test."""
    fallback = {
        "weak_topics": [],
        "strong_topics": [],
        "concept_gaps": "Review the explanations for every incorrect answer.",
        "time_management": "Keep an even pace; flag hard questions and return to them.",
        "guessing_pattern": "Not enough data to detect guessing.",
        "confidence": "Build confidence with one short recall test per day.",
        "advice": "Re-study the chapters you scored lowest on, then retest.",
    }
    return chat_json(
        "Analyse this test result and return JSON with keys weak_topics (array of "
        "strings), strong_topics (array), concept_gaps, time_management, "
        "guessing_pattern, confidence, advice.\n\n" + payload,
        "You are an expert learning analyst.",
        fallback,
    )
