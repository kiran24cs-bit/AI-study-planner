"""PDF report generation with ReportLab (timetable, performance, study report)."""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ACCENT = colors.HexColor("#6366f1")


def _document(title: str):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Generated on {date.today().strftime('%d %B %Y')}", styles["Normal"]),
        Spacer(1, 12),
    ]
    return buffer, doc, styles, story


def _table(data, col_widths=None):
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d4d4d8")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def timetable_pdf(user, tasks):
    """Full study timetable as a PDF."""
    buffer, doc, styles, story = _document(f"Study Timetable — {user.name}")

    if not tasks:
        story.append(Paragraph("No tasks scheduled yet.", styles["Normal"]))
    else:
        rows = [["Date", "Time", "Subject", "Chapter", "Task", "Min", "Status"]]
        for task in tasks:
            rows.append(
                [
                    task.day.strftime("%d %b"),
                    task.start_time,
                    Paragraph(task.subject_name, styles["BodyText"]),
                    Paragraph(task.chapter_name, styles["BodyText"]),
                    task.task_type.title(),
                    str(task.duration_minutes),
                    task.status.title(),
                ]
            )
        story.append(
            _table(rows, col_widths=[45, 40, 80, 130, 55, 30, 50])
        )

    doc.build(story)
    buffer.seek(0)
    return buffer


def performance_pdf(user, scores):
    """Test history and averages."""
    buffer, doc, styles, story = _document(f"Performance Report — {user.name}")

    if not scores:
        story.append(Paragraph("No tests taken yet.", styles["Normal"]))
    else:
        rows = [["Date", "Subject", "Chapter", "Score %", "Accuracy %", "Sec/Q"]]
        for score in scores:
            rows.append(
                [
                    score.created_at.strftime("%d %b"),
                    Paragraph(score.subject_name, styles["BodyText"]),
                    Paragraph(score.chapter_name, styles["BodyText"]),
                    f"{score.percentage:.1f}",
                    f"{score.accuracy:.1f}",
                    f"{score.speed:.1f}",
                ]
            )
        story.append(_table(rows, col_widths=[50, 90, 150, 55, 60, 45]))
        average = sum(s.percentage for s in scores) / len(scores)
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<b>Average score:</b> {average:.1f}%", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer


def study_report_pdf(user, stats, weak_topics, suggestions):
    """Combined study summary: stats, weak topics and AI advice."""
    buffer, doc, styles, story = _document(f"Study Report — {user.name}")

    rows = [["Metric", "Value"]] + [[k, str(v)] for k, v in stats.items()]
    story.append(_table(rows, col_widths=[220, 220]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Weak Topics", styles["Heading2"]))
    if weak_topics:
        for topic in weak_topics:
            story.append(
                Paragraph(
                    f"• {topic.topic} ({topic.subject_name}) — {topic.score:.0f}% accuracy",
                    styles["Normal"],
                )
            )
    else:
        story.append(Paragraph("No weak topics detected. Great work!", styles["Normal"]))

    story.append(Spacer(1, 16))
    story.append(Paragraph("AI Suggestions", styles["Heading2"]))
    for suggestion in suggestions:
        story.append(Paragraph(f"• {suggestion}", styles["Normal"]))

    doc.build(story)
    buffer.seek(0)
    return buffer
