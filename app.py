import streamlit as st
from agent import Call, execute, run_agent
from config import StudyError
from tools.progress_tracker import Progress
from tools.quiz_generator import evaluate
from tools.topic_recommender import CATALOG

st.set_page_config(page_title="Study Desk", page_icon="📘", layout="wide")
tracker = Progress()
store = st.session_state
for name, default in [("history", []), ("plans", {}), ("quizzes", {}), ("graded", {})]:
    store.setdefault(name, default)
if "next_subject" in store:
    store["active_subject"] = store.pop("next_subject")
with st.sidebar:
    st.title("Study Desk")
    subject = st.selectbox("Active subject", list(CATALOG), key="active_subject")
    st.caption("Subject guide")
    for topic in CATALOG[subject]:
        st.write("· " + topic)

st.title("Personal study assistant")
st.caption("Plan your preparation, practise exam questions and track what you have learned.")
chat, planner, quiz_tab, progress = st.tabs(["Study agent", "Study plan", "Quiz", "Progress"])


def retain(result):
    if result["tool"] == "plan":
        store.plans[result["subject"]] = result["data"]
    if result["tool"] == "quiz":
        store.quizzes[result["subject"]] = result["data"]


def manual(action, **kwargs):
    args = dict(action=action, subject=subject, days=1, minutes_per_day=60, questions=5, topics=[])
    try:
        result = execute(Call(**(args | kwargs)), tracker)
        retain(result)
        return result
    except StudyError as exc:
        st.error(str(exc))
        return None


with chat:
    st.subheader("What are you preparing for?")
    st.caption("Try “Help me prepare for DBMS in 2 hours” or “Make a 5-day SQL plan and a 3-question quiz.”")
    for item in store.history:
        with st.chat_message(item["role"]):
            st.markdown(item["text"])
            if item.get("trace"):
                st.caption("Tools used · " + " → ".join(item["trace"]))
    goal = st.chat_input("Enter your study goal", max_chars=3000)
    if goal:
        try:
            with st.spinner("Working on your study goal…"):
                message, results = run_agent(goal, subject, {s: list(ts) for s, ts in CATALOG.items()},
                                             store.history, lambda c: execute(c, tracker))
        except StudyError as exc:
            message, results = str(exc), []
        for r in results:
            retain(r)
        if results:
            store.next_subject = results[-1]["subject"]
        store.history.extend([{"role": "user", "text": goal},
                              {"role": "assistant", "text": message,
                               "trace": [r["tool"] + " (" + r["subject"] + ")" for r in results]}])
        st.rerun()

with planner:
    st.subheader(f"{subject} study plan")
    with st.form("planner"):
        left, right = st.columns(2)
        days = left.number_input("Study days", 1, 30, 1)
        minutes = right.number_input("Minutes per day", 5, 960, 60)
        build = st.form_submit_button("Create timetable")
    if build:
        manual("plan", days=days, minutes_per_day=minutes)
    if subject in store.plans:
        rows = store.plans[subject]
        st.caption("Minutes are measured from the start of each day's session.")
        st.dataframe([{"Day": r["day"], "Minutes": f"{r['start_min']}–{r['end_min']}",
                       "Session": r["activity"], "Task": r["task"]} for r in rows],
                     hide_index=True, width="stretch")

with quiz_tab:
    st.subheader(f"{subject} practice quiz")
    with st.form("new_quiz_" + subject):
        focus = st.multiselect("Focus topics (optional)", list(CATALOG[subject]))
        count = st.number_input("Number of questions", 1, 10, 5)
        new = st.form_submit_button("Generate quiz")
    if new:
        with st.spinner("Generating questions…"):
            manual("quiz", topics=focus, questions=count)
    quiz = store.quizzes.get(subject)
    if quiz:
        qid = quiz["id"]
        if qid not in store.graded:
            with st.form("attempt_" + qid):
                answers = []
                for i, q in enumerate(quiz["items"], 1):
                    options = q["options"]
                    answer = st.radio(f"{i}. {q['prompt']}", options, index=None, key=f"{qid}_{i}")
                    answers.append(options.index(answer) if answer is not None else None)
                submit = st.form_submit_button("Submit answers")
            if submit:
                try:
                    grade = evaluate(quiz, answers)
                    tracker.save_score(grade)
                    store.graded[qid] = grade
                    st.rerun()
                except StudyError as exc:
                    st.error(str(exc))
        else:
            grade = store.graded[qid]
            st.metric("Your score", f"{grade['score']} / {grade['total']}")
            for i, row in enumerate(grade["review"], 1):
                st.write(f"{i}. {row['prompt']}")
                if row["correct"]:
                    st.success("Correct · " + row["options"][row["chosen"]])
                else:
                    st.error("Your answer · " + row["options"][row["chosen"]])
                    st.write("Correct answer · " + row["options"][row["correct_index"]])
                st.caption(row["explanation"])

with progress:
    st.subheader(f"{subject} progress")
    try:
        state = tracker.read(subject)
    except StudyError as exc:
        st.error(str(exc))
        st.stop()
    completed = state["completed"]
    total = len(CATALOG[subject])
    left, right = st.columns(2)
    left.metric("Completed topics", f"{len(completed)} / {total}")
    right.metric("Quizzes submitted", len(state["scores"]))
    st.progress(len(completed) / total)
    remaining = [t for t in CATALOG[subject] if t not in completed]
    if remaining:
        with st.form("mark_" + subject):
            chosen = st.multiselect("Topics you have finished", remaining)
            save = st.form_submit_button("Mark complete")
        if save and manual("complete", topics=chosen):
            st.rerun()
    st.markdown("#### Completed topics")
    st.write(", ".join(completed) or "Your completed topics will appear here.")
    if state["scores"]:
        st.markdown("#### Quiz history")
        st.dataframe([{"Submitted (UTC)": r["date"][:19].replace("T", " "),
                       "Score": f"{r['score']} / {r['total']}"} for r in reversed(state["scores"])],
                     hide_index=True, width="stretch")
