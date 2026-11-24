import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from filelock import FileLock, Timeout
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from config import DATA, StudyError
from .topic_recommender import CATALOG


class Attempt(BaseModel):
    id: str
    score: int = Field(ge=0)
    total: int = Field(gt=0)
    date: str


class Record(BaseModel):
    completed: list[str] = Field(default_factory=list)
    scores: list[Attempt] = Field(default_factory=list)


class Journal(BaseModel):
    version: Literal[1]
    subjects: dict[str, Record]


class Progress:
    def __init__(self, path=None):
        self.path = Path(path or DATA / "progress.json")

    def _access(self, subject, change=None):
        if subject not in CATALOG:
            raise StudyError("Unknown subject.")
        temp = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with FileLock(str(self.path) + ".lock", timeout=5):
                journal = (Journal.model_validate_json(self.path.read_text(encoding="utf-8"))
                           if self.path.exists() else Journal(version=1, subjects={}))
                record = journal.subjects.setdefault(subject, Record())
                if (len(set(record.completed)) != len(record.completed)
                    or any(t not in CATALOG[subject] for t in record.completed)
                    or any(a.score > a.total for a in record.scores)):
                    raise StudyError("Invalid progress data. Restore a valid backup before saving.")
                if change:
                    change(record)
                    with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent,
                                                     encoding="utf-8", delete=False) as f:
                        temp = f.name
                        json.dump(journal.model_dump(), f, indent=2)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp, self.path)
                    temp = None
                return record.model_dump()
        except (ValidationError, UnicodeError) as exc:
            raise StudyError("Progress file is unreadable. Restore a valid backup before saving.") from exc
        except (OSError, Timeout) as exc:
            raise StudyError("Progress file is busy or inaccessible. Check permissions and retry.") from exc
        finally:
            if temp:
                Path(temp).unlink(missing_ok=True)

    def read(self, subject):
        return self._access(subject)

    def complete(self, subject, topics):
        if not topics or any(t not in CATALOG.get(subject, {}) for t in topics):
            raise StudyError("Select topics from the subject catalogue.")
        def change(record):
            record.completed = list(dict.fromkeys(record.completed + list(topics)))
        return self._access(subject, change)

    def save_score(self, result):
        def change(record):
            if all(a.id != result["id"] for a in record.scores):
                record.scores.append(Attempt(id=result["id"], score=result["score"],
                                             total=result["total"], date=datetime.now(timezone.utc).isoformat()))
        return self._access(result["subject"], change)
