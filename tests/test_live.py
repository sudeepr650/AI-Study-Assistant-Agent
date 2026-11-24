"""Opt-in check using your Gemini account and a temporary progress file."""
import os
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from agent import run_agent, execute
from tools.topic_recommender import CATALOG
from tools.progress_tracker import Progress


@unittest.skipUnless(os.getenv("RUN_LIVE_GEMINI") == "1", "set RUN_LIVE_GEMINI=1 for live Gemini calls")
class LiveGemini(unittest.TestCase):
    def test_goal_to_plan_and_quiz(self):
        with TemporaryDirectory() as d:
            tracker = Progress(Path(d) / "progress.json")
            message, results = run_agent("Create a 5-day SQL plan for 30 minutes per day and "
                                         "a 2-question SQL quiz on joins.", "Java", CATALOG, [],
                                         lambda c: execute(c, tracker))
            by_tool = {r["tool"]: r for r in results}
            self.assertTrue({"plan", "quiz"} <= by_tool.keys(), message)
            rows = by_tool["plan"]["data"]
            self.assertEqual(by_tool["plan"]["subject"], "SQL")
            self.assertEqual([r["end_min"] for r in rows if r["activity"] == "Revision"], [30]*5)
            self.assertEqual(len(by_tool["quiz"]["data"]["items"]), 2)
