from .topic_recommender import recommend
from config import StudyError


def plan(subject, days, minutes_per_day, focus=(), completed=()):
    if not 1 <= days <= 30 or not 5 <= minutes_per_day <= 960:
        raise StudyError("Use 1–30 days and 5–960 minutes per day.")
    topics = recommend(subject, days * minutes_per_day, focus, completed)
    rows = []
    for day in range(days):
        revision = max(1, minutes_per_day // 5)
        practice = max(1, minutes_per_day // 4)
        study = minutes_per_day - revision - practice
        block = [t for i, t in enumerate(topics) if i % days == day]
        if not block:
            block = [topics[day % len(topics)]]
        start = 0
        def add(kind, task, duration):
            nonlocal start
            rows.append(dict(day=day + 1, start_min=start, end_min=start + duration,
                             activity=kind, task=task))
            start += duration
        for i, topic in enumerate(block):
            duration = study // len(block) + int(i < study % len(block))
            add("Study", topic["topic"] + " — " + topic["objective"], duration)
        names = ", ".join(t["topic"] for t in block)
        add("Practice", "Solve exam questions on " + names, practice)
        add("Revision", "Recall the main ideas without notes: " + names, revision)
    return rows
