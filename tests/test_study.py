import json
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError
from streamlit.testing.v1 import AppTest
from agent import Call, Decision, execute, run_agent
from config import BASE, StudyError, generate
from tools.progress_tracker import Progress
from tools.quiz_generator import Questions, evaluate, generate_quiz
from tools.study_planner import plan
from tools.topic_recommender import recommend, CATALOG

Q = {"prompt": "Which join preserves unmatched rows from the left table?", "topic": "Joins",
     "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "RIGHT JOIN"],
     "correct_index": 1, "explanation": "A left join retains every left row and supplies NULL for unmatched right columns."}


def call(action):
    return dict(action=action, subject="SQL", days=5, minutes_per_day=60, questions=1, topics=["Joins"])


def response(**kwargs):
    schema = kwargs["config"].response_json_schema
    data = ({"clarification": "", "calls": [call("plan"), call("quiz")]}
            if schema["title"] == "Decision" else {"items": [Q]})
    return SimpleNamespace(text=json.dumps(data))


class StudyTests(unittest.TestCase):
    def test_budget(self):
        for subject in CATALOG:
            for days in range(1, 31):
                for minutes in (5, 20, 60, 120, 960):
                    rows = plan(subject, days, minutes)
                    self.assertTrue(all(r["end_min"] > r["start_min"] for r in rows))
                    self.assertEqual([r["end_min"] for r in rows if r["activity"] == "Revision"], [minutes]*days)

    def test_priority(self):
        self.assertEqual(recommend("SQL", 15, completed=["SELECT and filtering"])[0]["topic"], "Joins")
        self.assertGreater(len(recommend("SQL", 120)), len(recommend("SQL", 15)))

    def test_bad_quiz(self):
        for change in [dict(correct_index=4), dict(options=["A", "a", "C", "D"]), dict(options=["A"])]:
            with self.assertRaises(ValidationError):
                Questions(items=[Q | change])
        with self.assertRaises(StudyError):
            generate_quiz("SQL", ["Joins"], 2, lambda *_: Questions(items=[Q]))

    def test_scoring(self):
        quiz = generate_quiz("SQL", ["Joins"], 1, lambda *_: Questions(items=[Q]))
        self.assertEqual(evaluate(quiz, [1])["score"], 1)
        self.assertEqual(evaluate(quiz, [0])["score"], 0)
        with self.assertRaises(StudyError):
            evaluate(quiz, [None])

    def test_storage(self):
        with TemporaryDirectory() as d:
            path = Path(d)/"progress.json"
            tracker = Progress(path)
            with ThreadPoolExecutor(4) as pool:
                list(pool.map(lambda t: tracker.complete("SQL", [t]), CATALOG["SQL"]))
            for _ in range(2):
                tracker.save_score(dict(subject="SQL", id="a", score=0, total=1))
            state = Progress(path).read("SQL")
            self.assertEqual(set(state["completed"]), set(CATALOG["SQL"]))
            self.assertEqual(len(state["scores"]), 1)
            self.assertEqual(tracker.read("Java")["completed"], [])
            path.write_text("{")
            with self.assertRaises(StudyError):
                tracker.complete("SQL", ["Joins"])
            self.assertEqual(path.read_text(), "{")

    def test_routes(self):
        with TemporaryDirectory() as d:
            tracker = Progress(Path(d)/"p.json")
            calls = [call(name) for name in ["complete", "progress", "recommend"]]
            def decide(*_):
                return Decision(clarification="", calls=calls)
            msg, results = run_agent("Finished joins; show status and priorities", "SQL", CATALOG,
                                     [], lambda c: execute(c, tracker), decide)
            self.assertEqual([r["tool"] for r in results], ["complete","progress","recommend"])
            self.assertIn("1/6", msg)
            self.assertEqual(results[1]["data"]["completed"], ["Joins"])
            calls[0]["topics"] = ["Missing topic"]
            with self.assertRaises(StudyError):
                run_agent("test", "SQL", CATALOG, [], lambda c: self.fail(), decide)

    def test_clarification(self):
        decision = Decision(clarification="How many hours can you study?", calls=[])
        msg, rows = run_agent("unsure", "Java", CATALOG, [], lambda _: self.fail(), lambda *_: decision)
        self.assertEqual((msg, rows), (decision.clarification, []))

    def test_api_errors(self):
        with patch.dict(os.environ, GEMINI_API_KEY=""), self.assertRaisesRegex(StudyError, "API key"):
            generate("test", {}, Decision)
        with patch.dict(os.environ, GEMINI_API_KEY="test"):
            with patch("google.genai.models.Models.generate_content", return_value=SimpleNamespace(text="{")):
                with self.assertRaisesRegex(StudyError, "invalid"):
                    generate("test", {}, Decision)
            with patch("google.genai.models.Models.generate_content", side_effect=ConnectionError):
                with self.assertRaisesRegex(StudyError, "connection"):
                    generate("test", {}, Decision)

    def test_dashboard_workflow(self):
        with TemporaryDirectory() as d, patch.dict(os.environ, GEMINI_API_KEY="test"), \
             patch("tools.progress_tracker.DATA", Path(d)), \
             patch("google.genai.models.Models.generate_content", side_effect=response) as api:
            app = AppTest.from_file(str(BASE/"app.py"), default_timeout=15).run()
            app.chat_input[0].set_value("Give me a 5-day SQL plan and a quiz on joins").run()
            self.assertFalse(app.exception)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(app.selectbox[0].value, "SQL")
            self.assertEqual(len(app.dataframe[0].value), 15)
            def press(label):
                next(b for b in app.button if b.label == label).click().run()
            press("Submit answers")
            self.assertTrue(any("every question" in e.value for e in app.error))
            app.radio[0].set_value("INNER JOIN")
            press("Submit answers")
            self.assertTrue(any("Your answer" in e.value for e in app.error))
            self.assertIn("0 / 1", [m.value for m in app.metric])
            app.multiselect[-1].set_value(["Joins"])
            press("Mark complete")
            fresh = AppTest.from_file(str(BASE/"app.py")).run()
            fresh.selectbox[0].set_value("SQL").run()
            self.assertFalse(fresh.exception)
            self.assertIn("1 / 6", [m.value for m in fresh.metric])
            self.assertIn("0 / 1", fresh.dataframe[0].value["Score"].tolist())


if __name__ == "__main__":
    unittest.main()
