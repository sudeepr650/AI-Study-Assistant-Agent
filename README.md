# Personal AI Study Assistant Agent
A single-student Streamlit workspace for DBMS, Java, SQL and Computer Networks. Ask for a timetable, prioritised topics, a quiz, or a progress update. The chat displays the names of successfully executed tools.

## Run in VS Code on Windows
1. Install Python 3.11 or 3.12. Extract the ZIP. In VS Code choose **File → Open Folder** and select the folder containing `app.py`.
2. Open **Terminal → New Terminal**. In PowerShell run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). In the included `.env` file, paste it after `GEMINI_API_KEY=`. Keep the key private. You may change `GEMINI_MODEL` to a Gemini model available to your account that supports structured JSON output. An existing environment variable takes precedence over the file.
4. Start the app:
   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```
   Open the **Local URL** printed in the terminal. That address opens the app running on your computer. Keep the terminal open. Press Ctrl+C to stop.
5. On macOS/Linux use `python3 -m venv .venv` and replace the Windows Python path in the commands with `.venv/bin/python`.

## Try a complete session
- Ask **“Help me prepare for DBMS in 2 hours.”** Check the timetable in Study plan. Each day's offsets start at minute zero.
- Ask **“I have a Java exam tomorrow.”** The default budget is 60 minutes when hours are unspecified. Give an explicit daily budget to change it.
- Ask **“Create a 5-day SQL plan for 30 minutes a day and a 3-question quiz on joins.”** Open Quiz, answer each question, and submit. You can inspect the correct option and explanation after grading.
- Ask **“I finished joins in SQL. Mark it complete and show my progress.”** Reopen the app and select SQL to see the saved result. The sidebar switches to the subject of the last executed tool. For requests spanning subjects, select each subject to view its results.

## Agent workflow
1. The router sends the goal, selected subject, topic names and recent conversation to Gemini. Gemini returns a clarification or an ordered list of typed tool requests.
2. Pydantic validates the structure, supported actions, subjects, time limits and quiz size. Python checks all topic names before dispatch.
3. The executor invokes the named Python functions. The planner reads progress and recommendations before allocating its time budget. The quiz tool makes a separate Gemini request for fresh questions and validates the returned choices, answer indices, topics, question count and explanations.
4. The executor formats the actual tool results for chat and passes structured data to the dashboard. If a later tool fails, earlier successful results remain visible. Quiz grading and scores are computed locally from the student's submitted answers.
5. Topic completion and scored attempts are stored per subject in `data/progress.json`. File locking, atomic replacement and unique quiz IDs protect against concurrent updates and duplicate submissions.

## Phase record
| Phase | Files created or changed | Verification |
|---|---|---|
| 1. Setup | config.py, requirements.txt, .env, .gitignore | SDK initialization and missing-key error |
| 2. Routing | agent.py | Ordered two-tool dispatch with a controlled model decision |
| 3. Planning | tools/__init__.py, tools/study_planner.py, tools/topic_recommender.py, data/subjects.json | 600 daily-budget combinations and priority checks |
| 4. Quizzes | tools/quiz_generator.py | Validated sample questions, correct and incorrect grading, incomplete submission |
| 5. Persistence | tools/progress_tracker.py, data/progress.json | Fresh instance, duplicate submission and damaged JSON |
| 6. Dashboard | app.py, agent.py | Streamlit widget test, four tabs and timetable creation |
| 7. Integration | tests/test_study.py, tests/test_live.py, README.md; refinements to app.py, config.py, .env, requirements.txt and progress_tracker.py | Chat → plan and quiz → wrong answer review → completion → fresh dashboard. Real Python tools and temporary progress file; controlled Gemini responses. |

## Run tests
From the project folder run:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
The default suite uses controlled model responses, temporary files and Streamlit's AppTest. One live test is skipped by default. To check your real key, model access, routing and question generation, set the flag and repeat the test command:
```powershell
$env:RUN_LIVE_GEMINI="1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_live.py -v
Remove-Item Env:RUN_LIVE_GEMINI
```
This uses your Gemini quota. No live credentials were available during packaging.

## Operating notes
- Chat and quiz generation require internet access and a valid Gemini key. The timetable form and progress dashboard work locally without one. If Gemini reports a quota or model error, check the account's quota or update the model in .env, then restart.
- Topic priority follows the order in subjects.json. Completed topics move behind unfinished ones. Recommendations expand with available time. Requested quiz focus topics are passed directly to the generator.
- This is a personal app with one local progress file. A shared server would share that file between visitors. Chat, current plans, active quizzes and detailed answer reviews are session-only. Completed topics and quiz scores survive restarts.
- Validation checks the structure of generated questions. A plausible-looking answer key or explanation can still contain a subject-matter error.
- Back up data/progress.json to keep your progress. If it becomes unreadable, the app reports the issue without replacing it.
