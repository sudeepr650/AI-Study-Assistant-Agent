import json
from config import DATA, StudyError

CATALOG = json.loads((DATA / "subjects.json").read_text(encoding="utf-8"))


def recommend(subject, minutes, focus=(), completed=()):
    if subject not in CATALOG or minutes < 1:
        raise StudyError("Select a supported subject and a positive time budget.")
    topics = CATALOG[subject]
    if any(name not in topics for name in focus):
        raise StudyError("Choose a focus topic from the subject catalogue.")
    ordered = [name for name in topics if not focus or name in focus]
    ordered.sort(key=lambda name: name in completed)
    return [{"topic": name, "objective": topics[name]}
            for name in ordered[:max(1, minutes // 22)]]
