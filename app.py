import streamlit as st
import os
import re
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
from src.database import (initialize_database, connect, save_workspace_state, get_workspace_state, init_db, add_application, get_applications, update_application, delete_application,
                          init_planner_db, add_planner_task, get_planner_tasks, set_planner_task_done, delete_planner_task, update_planner_task,
                          init_profile_db, save_resume, get_profile, save_target_role, get_application_stats, get_task_stats,
                          init_mentor_db, save_mentor_message, get_mentor_messages, clear_mentor_messages,
                          init_roadmap_db, replace_roadmap_steps, get_roadmap_steps, set_roadmap_step_done)
from src.engine import (analyze_match, extract_text, make_interview_questions, evaluate_answer,
                        build_roadmap, make_gap_roadmap, build_topic_roadmap, parse_roadmap_topics)
from src.opportunities import OPPORTUNITIES
from src.live_jobs import fetch_remote_tech_jobs
from src.assistant import ask_mentor
import hmac
import logging

load_dotenv()
st.set_page_config(page_title="PlacementPilot AI", page_icon="🎯", layout="wide")


# Single-user workspace: require a password before exposing personal records.
password = os.environ.get("APP_PASSWORD", "")
if not password:
    st.error("Set APP_PASSWORD in Streamlit Secrets or .env before using this app.")
    st.stop()
if not st.session_state.get("authenticated"):
    with st.form("workspace_login"):
        entered = st.text_input("Workspace password", type="password")
        submitted = st.form_submit_button("Sign in")
    if submitted:
        if hmac.compare_digest(entered.encode(), password.encode()):
            st.session_state.authenticated = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()

@st.cache_resource
def _initialize_once():
    initialize_database()
    return True

try:
    _initialize_once()
    with connect() as con:
        con.execute("SELECT 1")
    if not st.session_state.get("workspace_loaded"):
        for key, value in get_workspace_state().items():
            if key in {"last_match", "last_jd", "gap_roadmap", "questions", "answer_idx", "interview_description"}:
                st.session_state[key] = value
        st.session_state.workspace_loaded = True
except Exception:
    logging.exception("Cloud database unavailable")
    st.error("Supabase is unavailable. Check DATABASE_URL, project status and network, then retry. No local database will be created.")
    if st.button("Retry connection"):
        st.rerun()
    st.stop()

def persist_state(key, value):
    save_workspace_state(key, value)
    st.session_state[key] = value

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@600;700;800&display=swap');
:root{--ink:#172033;--muted:#718096;--line:#e7ebf3;--violet:#6857e8;--cyan:#22b8cf}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1440px}
[data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#f7f8ff 0%,#f8fbff 45%,#fff 100%)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#111a2e,#1c2944);color:#fff}
[data-testid="stSidebar"] *{color:#eef2ff!important}
[data-testid="stSidebar"] [data-testid="stFileUploader"]{background:#253452;border:1px dashed #7183a8;border-radius:14px;padding:10px}
.hero{position:relative;overflow:hidden;padding:2rem 2.2rem;border-radius:24px;background:radial-gradient(circle at 85% 20%,#5d5be8 0,transparent 28%),linear-gradient(115deg,#111a31 0%,#273d68 60%,#315c83 100%);color:white;margin-bottom:1.2rem;box-shadow:0 18px 45px #1d2a4a24}
.hero h1{font-family:Manrope,sans-serif;font-size:2.35rem;font-weight:800;margin:0;letter-spacing:-1px}.hero p{color:#dce8ff;margin:.45rem 0 0;font-size:1rem}.eyebrow{font-size:.72rem;letter-spacing:2px;text-transform:uppercase;color:#b7c9ff;font-weight:800;margin-bottom:.45rem}
.section-title{font-family:Manrope,sans-serif;font-weight:800;font-size:1.28rem;color:#1c2944;margin:.4rem 0 .75rem}
div[data-testid="stMetric"]{background:white;border:1px solid var(--line);padding:16px 18px;border-radius:17px;box-shadow:0 7px 22px #253b6410}
div[data-testid="stMetric"] label{color:#75819a!important;font-weight:600}div[data-testid="stMetricValue"]{color:#202c47;font-weight:800}
.stTabs [data-baseweb="tab-list"]{gap:7px;background:#edf0fa;padding:7px;border-radius:15px}.stTabs [data-baseweb="tab"]{height:42px;border-radius:11px;padding:0 15px;font-weight:700}.stTabs [aria-selected="true"]{background:white!important;box-shadow:0 3px 12px #26365c16}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px;border-color:#e6eaf3;background:#fff;box-shadow:0 5px 18px #253b6408}
.jobcard{padding:1rem;border:1px solid var(--line);border-radius:15px;margin:.5rem 0;background:#fff}.muted{color:#64748b;font-size:.88rem}
div.stButton>button{border-radius:11px;font-weight:700;border:1px solid #dce2f0}div.stButton>button[kind="primary"]{background:linear-gradient(110deg,#6657e8,#3186d5);border:0;color:#fff}
[data-testid="stProgressBar"]>div>div{background:linear-gradient(90deg,#6958e8,#24b9cf)}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><div class="eyebrow">YOUR CAREER, IN CONTROL</div><h1>PlacementPilot AI <span style="font-size:1.4rem">✦</span></h1><p>One workspace to track your progress, sharpen your profile, discover opportunities and land your next role.</p></div>', unsafe_allow_html=True)

profile = get_profile()
with st.sidebar:
    st.markdown("## ✦ Your workspace")
    st.success("Supabase PostgreSQL connected")
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()
    if profile and profile[1]:
        st.success("Resume saved in the app database")
        st.caption(f"📄 {profile[0]} · saved {profile[2]}")
        if st.button("Replace saved resume", use_container_width=True): st.session_state.show_resume_uploader = True
    else:
        st.info("Upload once. Your parsed resume will be saved for future visits.")
        st.session_state.show_resume_uploader = True
    if st.session_state.get("show_resume_uploader", False):
        uploaded_resume = st.file_uploader("Upload resume (PDF/DOCX)", type=["pdf", "docx"], key="resume_upload")
        if uploaded_resume:
            try:
                parsed = extract_text(uploaded_resume.getvalue(), uploaded_resume.name)
                if not parsed.strip(): st.error("No readable text found. If this is a scanned PDF, run OCR first.")
                else:
                    save_resume(uploaded_resume.name, parsed)
                    st.session_state.show_resume_uploader = False
                    st.success("Resume saved. The app will reuse it automatically.")
                    st.rerun()
            except Exception as e: st.error(f"Could not read resume: {e}")
    st.divider()
    roles = ["AI Engineer", "Generative AI Engineer", "Machine Learning Engineer", "Data Scientist", "Computer Vision Engineer", "NLP Engineer"]
    saved_role = profile[3] if profile and len(profile)>3 and profile[3] in roles else "AI Engineer"
    target_role = st.selectbox("Target role", roles, index=roles.index(saved_role))
    if target_role != saved_role: save_target_role(target_role)
    st.caption("Your plan is flexible. Change your target role or pace whenever you need.")

resume_text = profile[1] if profile else ""

pages = st.tabs(["🏠 Overview", "📄 Job Match", "🧠 Flexible Roadmap", "🗓️ Day Planner", "🔎 Jobs & Internships", "🎤 Mock Interview", "📌 Applications", "✨ AI Mentor", "📈 Progress"])

with pages[0]:
    apps = get_applications(); total = len(apps)
    interviews = sum(1 for a in apps if a[5] in ["Interview", "Technical Round", "HR Round", "Offer"])
    offers = sum(1 for a in apps if a[5] == "Offer")
    today_tasks = get_planner_tasks(str(date.today())); done = sum(1 for t in today_tasks if t[6])
    week_start = date.today() - timedelta(days=date.today().weekday()); week_end = week_start + timedelta(days=6)
    stats = get_task_stats(str(week_start), str(week_end)) or (0,0,0,0)
    tasks_total, tasks_done, mins_total, mins_done = [int(x or 0) for x in stats]
    st.markdown('<div class="section-title">Your placement snapshot</div>', unsafe_allow_html=True)
    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Applications", total, help="Roles saved or applied to")
    m2.metric("Interview pipeline", interviews)
    m3.metric("Offers", offers)
    m4.metric("Today's tasks", f"{done}/{len(today_tasks)}")
    m5.metric("Resume status", "Ready" if resume_text else "Missing")
    left,right = st.columns([1.25,1])
    with left:
        st.markdown('<div class="section-title">Application pipeline</div>', unsafe_allow_html=True)
        status_counts = dict(get_application_stats())
        pipeline_order = ["Saved","Applied","Assessment","Interview","Technical Round","HR Round","Offer","Rejected"]
        chart_data = {"Stage":pipeline_order,"Applications":[status_counts.get(x,0) for x in pipeline_order]}
        st.bar_chart(chart_data, x="Stage", y="Applications", color="#6c63e8", height=260)
    with right:
        st.markdown("<div class=\"section-title\">This week\'s learning rhythm</div>", unsafe_allow_html=True)
        pct = round(tasks_done/tasks_total*100) if tasks_total else 0
        st.metric("Tasks completed", f"{tasks_done}/{tasks_total}", f"{pct}% completion")
        st.progress(pct/100 if tasks_total else 0)
        st.write(f"**Planned:** {mins_total//60}h {mins_total%60}m  ·  **Completed:** {mins_done//60}h {mins_done%60}m")
        st.caption(f"Week: {week_start.strftime('%d %b')} – {week_end.strftime('%d %b')}")
    st.markdown("<div class=\"section-title\">Today\'s action list</div>", unsafe_allow_html=True)
    if today_tasks:
        for t in today_tasks:
            st.write(("☑️" if t[6] else "◻️") + f" **{t[2]}** · {t[4]} min · {t[3]}")
    else: st.info("Your day is clear. Add a task in Day Planner or send tasks from your roadmap.")
    roadmap_snapshot = get_roadmap_steps()
    st.markdown('<div class="section-title">Current learning progress</div>', unsafe_allow_html=True)
    if roadmap_snapshot:
        roadmap_done = sum(1 for row in roadmap_snapshot if row[6])
        roadmap_pct = round(roadmap_done / len(roadmap_snapshot) * 100)
        rp1, rp2, rp3 = st.columns(3)
        rp1.metric("Roadmap completion", f"{roadmap_pct}%")
        rp2.metric("Steps completed", f"{roadmap_done}/{len(roadmap_snapshot)}")
        rp3.metric("Topics in progress", len(set(row[1] for row in roadmap_snapshot if not all(x[6] for x in roadmap_snapshot if x[1] == row[1]))))
        st.progress(roadmap_pct / 100)
        next_steps = [row for row in roadmap_snapshot if not row[6]][:3]
        if next_steps:
            st.caption("Next up")
            for row in next_steps: st.write(f"• **{row[1]}:** {row[2]} · {row[4]}")
        else: st.success("All roadmap steps completed. Add new topics to continue learning.")
    else:
        st.info("No roadmap yet. Add your own topics in Flexible Roadmap; completion will be tracked here and in Progress.")
    if resume_text:
        st.success(f"Resume connected: {profile[0]} · {len(resume_text):,} characters parsed and saved. Job matches will use this saved profile automatically.")
    else: st.warning("Upload your resume once from the sidebar to activate automatic job matching.")

with pages[1]:
    st.subheader("Resume vs Job Description")
    jd = st.text_area("Paste a complete job description", height=220, value=st.session_state.get("last_jd", ""), placeholder="Responsibilities, required skills, qualifications...")
    if st.button("Analyze my match", type="primary", disabled=not jd.strip()):
        resume = resume_text
        if not resume: st.warning("Upload your resume in the sidebar first.")
        else:
            persist_state("last_match", analyze_match(resume, jd))
            persist_state("last_jd", jd)
    if "last_match" in st.session_state:
        r = st.session_state.last_match
        a,b,c = st.columns(3); a.metric("Resume match", f"{r['score']}%"); b.metric("Matched skills", len(r['matched'])); c.metric("Skill gaps", len(r['missing']))
        st.progress(r['score']/100)
        st.markdown(f"**Quick assessment:** {r.get('summary', '')}")
        for reason in r.get("reasons", []):
            st.write("• " + reason)
        left,right = st.columns(2)
        with left: st.markdown("**Skills detected in both**"); st.success(", ".join(r['matched']) if r['matched'] else "No direct overlap found")
        with right: st.markdown("**Skills missing from resume**"); st.warning(", ".join(r['missing']) if r['missing'] else "No gaps found in built-in skill list")
        for item in r['actions']: st.write("• " + item)
        if r['missing']:
            if st.button("Create a learning roadmap for these skill gaps", type="primary"):
                persist_state('gap_roadmap', make_gap_roadmap(r['missing']))
                st.success("Skill-gap roadmap created. Open Flexible Roadmap to set your pace and schedule.")
        st.caption("The score is a transparent heuristic, not an employer ATS score or a hiring prediction.")

with pages[2]:
    st.subheader(f"Flexible learning roadmap · {target_role}")
    st.write("Enter the exact topics you want to learn. The roadmap will be built from those topics—not from a fixed role template.")
    p1,p2,p3 = st.columns(3)
    with p1: weekly_hours = st.slider("Study hours per week", 2, 40, 10)
    with p2: study_days = st.slider("Study days per week", 1, 7, 5)
    with p3: start_on = st.date_input("Start date", value=date.today(), key="roadmap_start_date")
    weekdays = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    selected_days = st.multiselect("Which days are you available?", weekdays, default=weekdays[:study_days], key="roadmap_available_days")
    topics_text = st.text_area(
        "Topics I want to learn (comma-separated or one per line)",
        placeholder="Example: Hugging Face, LangChain, RAG, Docker, Kubernetes, DSA",
        height=110,
        key="roadmap_topics_input",
    )
    current_skills = st.text_area(
        "Topics/skills I already know (optional)",
        placeholder="Example: Python, SQL, Machine Learning",
        height=75,
        key="roadmap_current_skills_input",
    )
    if st.button("Generate roadmap for my topics", type="primary"):
        topics = parse_roadmap_topics(topics_text)
        if not topics:
            st.error("Enter at least one topic you want to learn.")
        elif not selected_days:
            st.error("Select at least one available study day.")
        else:
            topic_plans = build_topic_roadmap(topics)
            schedule_rows = []
            day_cursor = start_on
            daily_capacity = max(0.5, weekly_hours / len(selected_days))
            for plan in topic_plans:
                for step in plan["steps"] + [f"Build deliverable: {plan['deliverable']}"]:
                    while day_cursor.strftime("%A") not in selected_days:
                        day_cursor += timedelta(days=1)
                    schedule_rows.append({
                        "topic": plan["topic"], "step": step,
                        "deliverable": plan["deliverable"],
                        "date": str(day_cursor), "hours": min(1.5, daily_capacity),
                    })
                    day_cursor += timedelta(days=1)
            replace_roadmap_steps(schedule_rows)
            st.success(f"Created a personalized roadmap with {len(schedule_rows)} steps across {len(topic_plans)} topics.")
            st.rerun()

    roadmap_rows = get_roadmap_steps()
    if roadmap_rows:
        total = len(roadmap_rows)
        completed = sum(1 for row in roadmap_rows if row[6])
        pct = round(completed / total * 100)
        st.markdown("#### Your saved roadmap")
        st.metric("Overall roadmap progress", f"{completed}/{total} steps", f"{pct}% complete")
        st.progress(pct / 100)
        topics = list(dict.fromkeys(row[1] for row in roadmap_rows))
        for topic in topics:
            topic_rows = [row for row in roadmap_rows if row[1] == topic]
            topic_done = sum(1 for row in topic_rows if row[6])
            with st.expander(f"{topic} · {topic_done}/{len(topic_rows)} steps complete", expanded=True):
                for row in topic_rows:
                    step_id, _, step, deliverable, planned_date, hours, is_done = row
                    c1, c2 = st.columns([4, 1])
                    checked = c1.checkbox(step, value=bool(is_done), key=f"roadmap_step_{step_id}")
                    c2.caption(f"{planned_date} · {hours:g}h")
                    if checked != bool(is_done):
                        set_roadmap_step_done(step_id, checked)
                        st.rerun()
                st.caption(f"Portfolio outcome: {topic_rows[0][3]}")
        st.divider()
        if st.button("Add incomplete roadmap steps to Day Planner", type="primary"):
            for row in roadmap_rows:
                if not row[6]:
                    add_planner_task(row[4], row[2], "Roadmap", int(row[5] * 60), f"Topic: {row[1]}")
            st.success("Incomplete roadmap steps added to your Day Planner.")
    else:
        st.info("Your roadmap will appear here after you enter your topics and generate it.")
    if "gap_roadmap" in st.session_state:
        st.markdown("#### Skill gaps from your job description")
        for gap in st.session_state.gap_roadmap:
            with st.expander(f"{gap['skill']} — learning path", expanded=True):
                for n, step in enumerate(gap['steps'],1): st.write(f"{n}. {step}")
                st.caption(gap['deliverable'])

with pages[3]:
    st.subheader("Your day planner")
    chosen_date = st.date_input("Plan for date", value=date.today(), key="planner_date")
    with st.form("add_day_task", clear_on_submit=True):
        t1,t2,t3 = st.columns([2,1,1])
        task_title = t1.text_input("Task")
        category = t2.selectbox("Category", ["Learning", "DSA", "Project", "Job Application", "Interview Prep", "Revision", "Break"])
        duration = t3.number_input("Minutes", min_value=15, max_value=480, value=60, step=15)
        task_notes = st.text_input("Notes (optional)")
        if st.form_submit_button("Add task", type="primary"):
            if task_title.strip(): add_planner_task(str(chosen_date), task_title.strip(), category, int(duration), task_notes); st.rerun()
            else: st.error("Enter a task name.")
    tasks = get_planner_tasks(str(chosen_date))
    if tasks:
        completed_minutes = sum(t[4] for t in tasks if t[6]); total_minutes = sum(t[4] for t in tasks)
        a,b,c = st.columns(3); a.metric("Tasks",len(tasks)); b.metric("Completed",sum(1 for t in tasks if t[6])); c.metric("Time completed",f"{completed_minutes//60}h {completed_minutes%60}m")
        st.progress(sum(1 for t in tasks if t[6])/len(tasks))
        for task in tasks:
            with st.container(border=True):
                x1,x2,x3 = st.columns([0.12,0.68,0.2])
                checked = x1.checkbox("Done", value=bool(task[6]), key=f"done_{task[0]}", label_visibility="collapsed")
                x2.markdown(("~~"+task[2]+"~~") if checked else f"**{task[2]}**")
                x2.caption(f"{task[3]} · {task[4]} min" + (f" · {task[5]}" if task[5] else ""))
                if checked != bool(task[6]): set_planner_task_done(task[0], checked); st.rerun()
                with st.expander("Reschedule / adjust duration"):
                    e1,e2=st.columns(2)
                    moved_date=e1.date_input("Move to date", value=date.fromisoformat(task[1]), key=f"move_date_{task[0]}")
                    moved_duration=e2.number_input("Duration (minutes)", min_value=15, max_value=480, value=int(task[4]), step=15, key=f"move_duration_{task[0]}")
                    if st.button("Save task changes", key=f"save_task_{task[0]}"):
                        update_planner_task(task[0], str(moved_date), int(moved_duration)); st.rerun()
                if x3.button("Delete", key=f"del_{task[0]}"): delete_planner_task(task[0]); st.rerun()
    else: st.info("No tasks planned for this day. Add a task or send items from your roadmap.")

with pages[4]:
    st.subheader("Jobs & internships")
    st.write("Curated opportunities checked on 11 November 2026. Listings can close or change; verify eligibility and status on the employer's page before applying.")
    f1,f2,f3 = st.columns(3)
    type_filter = f1.selectbox("Opportunity type", ["All", "Internship", "Full-time"])
    location_filter = f2.selectbox("Location", ["All", "Pune", "Remote / Other"])
    query = f3.text_input("Search company or role")
    matches = []
    for job in OPPORTUNITIES:
        if type_filter != "All" and job['type'] != type_filter: continue
        is_pune = "pune" in job['location'].lower() or "bhosari" in job['location'].lower() or "balewadi" in job['location'].lower()
        if location_filter == "Pune" and not is_pune: continue
        if location_filter == "Remote / Other" and is_pune: continue
        if query and query.lower() not in (job['company']+job['role']+job['fit']+job['location']).lower(): continue
        matches.append(job)
    st.caption(f"Showing {len(matches)} curated opportunities")
    if not resume_text: st.info("Upload your resume once in the sidebar. Every job card will then show a resume match score and a short skill-gap summary.")
    for idx, job in enumerate(matches):
        jd_text = " ".join([job['role'], job['company'], job['fit'], job['eligibility'], job['location']])
        match = analyze_match(resume_text, jd_text) if resume_text else None
        with st.container(border=True):
            h1,h2 = st.columns([3,1]); h1.markdown(f"**{job['role']}** · {job['company']}"); h2.markdown(f"`{job['type']}`")
            st.write(f"📍 {job['location']} · {job['mode']} · {job['duration']}")
            if match:
                score_col,detail_col = st.columns([1,3])
                score_col.metric("Resume match", f"{match['score']}%")
                score_col.progress(match['score']/100)
                detail_col.markdown(f"**Quick match summary:** {match['summary']}")
                for reason in match.get("reasons", [])[:2]: detail_col.caption("• " + reason)
                if match['missing']:
                    detail_col.caption("**Top skills to evidence:** " + ", ".join(match['missing'][:4]))
                else:
                    detail_col.caption("No missing skills found in the built-in vocabulary; review the full role description too.")
                with st.expander("See matched and missing skills"):
                    st.write("**Matched:** " + (", ".join(match['matched']) or "No direct skill overlap detected"))
                    st.write("**Missing:** " + (", ".join(match['missing']) or "None detected"))
            st.write(f"**Eligibility:** {job['eligibility']}")
            st.write(f"**Compensation:** {job['pay']}")
            st.write(f"**Fit notes:** {job['fit']}")
            st.markdown(f"[Open application / employer details]({job['url']}) · <span class='muted'>{job['source']}</span>", unsafe_allow_html=True)
            if st.button("Save to my application tracker", key=f"save_job_{idx}"):
                note = f"Saved from PlacementPilot job search. Resume match: {match['score']}%" if match else "Saved from PlacementPilot job search"
                add_application(job['company'], job['role'], job['location'], str(date.today()), "Saved", job['url'], note)
                st.success("Saved to Applications")
    if not matches: st.info("No curated roles match those filters. Try All locations or a broader search.")

    st.divider()
    st.markdown("### Fresh remote AI / ML jobs")
    st.caption("Live remote listings from Remotive. The curated Pune/India list above is a manually maintained snapshot; this refresh button updates the live remote feed only.")
    @st.cache_data(ttl=21600, show_spinner=False)
    def get_cached_remote_jobs():
        return fetch_remote_tech_jobs()

    refresh_col, refreshed_col = st.columns([1, 3])
    with refresh_col:
        if st.button("↻ Refresh live jobs", key="refresh_remote_jobs", use_container_width=True):
            get_cached_remote_jobs.clear()
            st.session_state["remote_jobs_just_refreshed"] = True
            st.rerun()
    with refreshed_col:
        st.caption("Automatic cache: 6 hours · Manual refresh clears the cache and requests the feed again.")

    if st.session_state.pop("remote_jobs_just_refreshed", False):
        st.success("Live job feed refreshed. New listings appear when the source has published them.")

    try:
        with st.spinner("Fetching the latest remote AI / ML listings…"):
            remote_jobs = get_cached_remote_jobs()
        remote_query = st.text_input("Filter live remote jobs", placeholder="e.g. LLM, Python, computer vision", key="live_remote_query")
        remote_limit = st.selectbox("Show live listings", [10, 20, 40], index=1, key="live_remote_limit")
        if remote_query:
            remote_jobs = [j for j in remote_jobs if remote_query.casefold() in (j['role'] + " " + j['company'] + " " + j.get('description','')).casefold()]
        st.caption(f"{len(remote_jobs)} matching live-feed roles · Remotive source")
        if not remote_jobs:
            st.info("No matching remote AI / ML roles were returned. Try a broader keyword or check again later.")
        for idx, job in enumerate(remote_jobs[:remote_limit]):
            jd_text = re.sub(r"<[^>]+>", " ", job.get("description", ""))
            match = analyze_match(resume_text, f"{job['role']} {job['fit']} {jd_text}") if resume_text else None
            with st.container(border=True):
                jh, jt = st.columns([3,1]); jh.markdown(f"**{job['role']}** · {job['company']}"); jt.markdown("`LIVE · REMOTE`")
                st.write(f"🌍 {job['location']} · {job['type']} · Posted: {job.get('published') or 'Date not supplied'}")
                st.write(f"**Compensation:** {job['pay']}")
                if match:
                    st.markdown(f"**Resume fit: {match['score']}%** — {match['summary']}")
                    short_reasons = match.get("reasons", [])[:2]
                    for reason in short_reasons: st.caption("• " + reason)
                st.markdown(f"[View role and apply on Remotive]({job['url']}) · Source: Remotive")
                if st.button("Save remote role", key=f"save_remote_{idx}"):
                    add_application(job['company'], job['role'], job['location'], str(date.today()), "Saved", job['url'], "Saved from live Remotive feed")
                    st.success("Saved to Applications")
    except Exception as exc:
        st.warning(f"The live remote feed is temporarily unavailable ({exc}). Your curated Pune listings and external job-search links are still available below.")
    st.markdown("**More India-focused live searches:** [Pune AI/ML internships](https://interndoor.com/roles/ai-machine-learning-in-pune) · [LinkedIn AI/ML jobs in Pune](https://www.linkedin.com/jobs/search/?keywords=AI%20ML%20Engineer&location=Pune%2C%20Maharashtra%2C%20India) · [Indeed AI/ML internships in Pune](https://in.indeed.com/q-ai-ml-internship-l-pune,-maharashtra-jobs.html)")

with pages[5]:
    st.subheader("AI mock interview")
    interview_jd = st.text_area("Paste job description (optional)", key="interview_jd", height=130, value=st.session_state.get("interview_description", ""))
    if st.button("Generate interview questions", type="primary"):
        persist_state("answer_idx", 0); persist_state("questions", make_interview_questions(target_role, interview_jd, resume_text)); persist_state("interview_description", interview_jd)
    if "questions" in st.session_state:
        qs = st.session_state.questions; idx = st.session_state.get("answer_idx",0)
        st.caption(f"Question {idx+1} of {len(qs)}"); st.markdown(f"### {qs[idx]}")
        answer = st.text_area("Your answer", key=f"answer_{idx}", height=160)
        if st.button("Evaluate answer", disabled=not answer.strip()):
            ev = evaluate_answer(answer, qs[idx], interview_jd); st.metric("Answer completeness",f"{ev['score']}%"); st.write("**What worked:**",ev['strength']); st.write("**Improve:**",ev['improve']); st.write("**Try adding:**",ev['missing'])
        p,n = st.columns(2)
        if p.button("← Previous",disabled=idx==0): persist_state("answer_idx", idx-1); st.rerun()
        if n.button("Next →",disabled=idx>=len(qs)-1): persist_state("answer_idx", idx+1); st.rerun()

with pages[6]:
    st.subheader("Application pipeline")
    with st.form("new_application", clear_on_submit=True):
        x1,x2,x3=st.columns(3); company=x1.text_input("Company *"); role=x2.text_input("Role *",value=target_role); location=x3.text_input("Location",value="Pune / Remote")
        y1,y2,y3=st.columns(3); applied=y1.date_input("Applied on"); status=y2.selectbox("Status",["Saved","Applied","Assessment","Interview","Technical Round","HR Round","Offer","Rejected"]); link=y3.text_input("Job URL")
        notes=st.text_input("Notes / follow-up")
        if st.form_submit_button("Add application",type="primary"):
            if company.strip() and role.strip(): add_application(company,role,location,str(applied),status,link,notes); st.success("Saved"); st.rerun()
            else: st.error("Company and role are required.")
    rows=get_applications()
    if rows:
        st.dataframe([{"ID":r[0],"Company":r[1],"Role":r[2],"Location":r[3],"Applied":r[4],"Status":r[5],"URL":r[6],"Notes":r[7]} for r in rows],use_container_width=True,hide_index=True)
        ids=[r[0] for r in rows]; chosen=st.selectbox("Select application",ids,format_func=lambda i: next(f"{r[1]} — {r[2]} ({r[5]})" for r in rows if r[0]==i)); selected=next(r for r in rows if r[0]==chosen)
        u1,u2=st.columns([3,1])
        new_status=u1.selectbox("Update status",["Saved","Applied","Assessment","Interview","Technical Round","HR Round","Offer","Rejected"],index=["Saved","Applied","Assessment","Interview","Technical Round","HR Round","Offer","Rejected"].index(selected[5]))
        if u1.button("Update status"): update_application(chosen,new_status); st.rerun()
        if u2.button("Delete application"): delete_application(chosen); st.rerun()
    else: st.info("No applications yet. Save a role from Jobs & Internships or add one manually.")


with pages[7]:
    st.subheader("Your personal AI placement mentor")
    st.write("Ask for help at any stage—from understanding a concept or fixing a traceback to tailoring an application and preparing for an interview. The mentor uses your saved resume, target role and placement progress as context.")

    # Provider credentials are read from environment / Streamlit secrets or held in this browser session only.
    def _secret(name, default=""):
        try:
            return st.secrets.get(name, default)
        except Exception:
            return default

    default_provider = "Groq" if (os.getenv("GROQ_API_KEY") or _secret("GROQ_API_KEY")) and not (os.getenv("OPENAI_API_KEY") or _secret("OPENAI_API_KEY")) else "OpenAI"
    provider = st.selectbox("AI provider", ["OpenAI", "Groq"], index=0 if default_provider == "OpenAI" else 1, key="mentor_provider")
    if provider == "Groq":
        key_default = os.getenv("GROQ_API_KEY") or _secret("GROQ_API_KEY", "")
        model_default = os.getenv("GROQ_MODEL") or _secret("GROQ_MODEL", "openai/gpt-oss-20b")
        base_default = "https://api.groq.com/openai/v1"
    else:
        key_default = os.getenv("OPENAI_API_KEY") or _secret("OPENAI_API_KEY", "")
        model_default = os.getenv("OPENAI_MODEL") or _secret("OPENAI_MODEL", "gpt-4o-mini")
        base_default = os.getenv("OPENAI_BASE_URL") or _secret("OPENAI_BASE_URL", "")
    config_col1, config_col2 = st.columns([1, 2])
    with config_col1:
        api_key = st.text_input(f"{provider} API key", value=key_default, type="password", key=f"mentor_key_{provider}", help="Kept in this app session only. It is never saved in the Supabase database.")
    with config_col2:
        model_name = st.text_input("Model name", value=model_default, key=f"mentor_model_{provider}")
        if provider == "OpenAI":
            base_url = st.text_input("Custom API base URL (optional)", value=base_default, key="mentor_base_url")
        else:
            base_url = base_default
    consent = st.checkbox("I understand that my chat and saved resume context will be sent to the selected AI provider when I ask a question.", value=False, key="mentor_data_consent")
    if not api_key:
        st.info("Add an API key above, or configure OPENAI_API_KEY / GROQ_API_KEY in your environment or Streamlit secrets to enable live AI responses.")
    if not consent:
        st.caption("Your resume stays in the app database until you choose to ask the AI mentor and approve sending its context.")

    quick_actions = [
        ("🧾 Resume audit", "Audit my saved resume for the target role. Give an honest ATS-readability review, strongest evidence, missing keywords, weak bullets and the top 5 edits in priority order. Do not invent experience."),
        ("🧭 What should I learn next?", "Using my saved resume and target role, identify my highest-impact skill gaps. Give me a prioritized 2-week learning plan with prerequisites, hands-on exercises and a portfolio deliverable."),
        ("🛠️ I'm stuck / debug help", "Act as my technical debugging mentor. First tell me exactly what code, traceback, command and expected output you need. Then help me isolate the issue one test at a time."),
        ("🎤 Interview preparation", "Start a realistic interview for my target role using my resume. Ask one question at a time. Wait for my answer, then evaluate technical correctness, clarity, depth and trade-offs."),
        ("🚀 Project portfolio review", "Review the projects in my saved resume for AI/ML/GenAI placements. Tell me what is weak, what advanced feature would make each stronger, and propose one standout project with architecture, milestones and evaluation metrics."),
        ("📨 Job application kit", "Help me prepare a truthful application for my target role. Give a reusable cover-letter structure, recruiter message and role-tailoring checklist. Ask me for a specific job description if required."),
        ("📅 14-day placement sprint", "Create a realistic 14-day placement sprint based on my saved profile and target role. Balance DSA, AI/ML fundamentals, projects, applications and interview practice. Give daily tasks, time estimates and measurable outcomes."),
        ("📊 Weekly progress review", "Review my current application pipeline and planner activity. Identify bottlenecks, what I should stop/start/continue, and three measurable priorities for next week."),
    ]
    st.markdown("#### Start with a guided action")
    quick_cols = st.columns(4)
    for i, (label, prompt) in enumerate(quick_actions):
        if quick_cols[i % 4].button(label, key=f"mentor_quick_{i}", use_container_width=True, disabled=not (api_key and consent)):
            st.session_state.mentor_pending_prompt = prompt
            st.rerun()

    st.markdown("#### Conversation")
    history = get_mentor_messages(limit=40)
    if not history:
        st.markdown("<div class='jobcard'><b>Welcome to your placement mentor.</b><br><span class='muted'>Try a guided action above, or ask a question in your own words. You can return later; the recent conversation is saved in this app database.</span></div>", unsafe_allow_html=True)
    else:
        for msg_role, msg_content, _created in history:
            with st.chat_message("assistant" if msg_role == "assistant" else "user"):
                st.markdown(msg_content)

    with st.form("mentor_message_form", clear_on_submit=True):
        user_prompt = st.text_area("Ask your mentor", placeholder="Example: I understand RAG basics but get confused about chunking and retrieval evaluation. Teach me with a practical example...", height=110)
        send = st.form_submit_button("Send to AI mentor", type="primary", disabled=not (api_key and consent))
    pending_prompt = st.session_state.pop("mentor_pending_prompt", None)
    prompt_to_send = pending_prompt or (user_prompt.strip() if send else "")
    if prompt_to_send:
        current_apps = get_applications()
        app_summary = ", ".join(f"{a[1]}: {a[2]} ({a[5]})" for a in current_apps[:15]) or "No applications tracked yet"
        todays = get_planner_tasks(str(date.today()))
        planner_summary = "; ".join(f"{t[2]} ({'done' if t[6] else 'pending'}, {t[4]} min)" for t in todays) or "No tasks planned for today"
        context = {
            "resume_name": profile[0] if profile else "Not uploaded",
            "resume_text": resume_text,
            "target_role": target_role,
            "application_summary": app_summary,
            "planner_summary": planner_summary,
        }
        save_mentor_message("user", prompt_to_send)
        try:
            answer = ask_mentor(
                api_key=api_key,
                model=model_name,
                base_url=base_url,
                messages=[{"role": role, "content": content} for role, content, _ in get_mentor_messages(limit=16)],
                context=context,
            )
            save_mentor_message("assistant", answer)
            st.rerun()
        except Exception as exc:
            st.error(f"The AI request could not be completed: {exc}")
            st.caption("Check your API key, model name, provider quota and internet connection. Your question remains in the saved conversation; you can send it again after fixing the settings.")
    with st.expander("Turn AI advice into a day-planner task"):
        st.caption("Choose one concrete next action from the mentor's advice and add it to your schedule. Nothing is added until you confirm.")
        with st.form("mentor_to_planner", clear_on_submit=True):
            action_title = st.text_input("Next action", placeholder="Example: Build a FAISS retriever and test top-k results")
            action_col1, action_col2, action_col3 = st.columns(3)
            action_date = action_col1.date_input("Schedule for", value=date.today())
            action_minutes = action_col2.number_input("Duration (minutes)", min_value=15, max_value=480, value=60, step=15)
            action_category = action_col3.selectbox("Category", ["Learning", "DSA", "Project", "Job Application", "Interview Prep", "Revision"])
            add_action = st.form_submit_button("Add confirmed action to planner", type="primary")
            if add_action:
                if action_title.strip():
                    add_planner_task(str(action_date), action_title.strip(), action_category, int(action_minutes), "Created from AI Mentor advice")
                    st.success("Added to your Day Planner.")
                else:
                    st.error("Enter an action before adding it.")
    if history and st.button("Clear mentor conversation", type="secondary"):
        clear_mentor_messages()
        st.rerun()
    st.caption("Privacy: recent chat messages are stored in the app's Supabase database. The API key is not stored there. Your resume and chat are transmitted to the provider only when you send a prompt with consent enabled. Use a private deployment and review your provider's data policy.")



with pages[8]:
    st.subheader("Your learning progress")
    progress_rows = get_roadmap_steps()
    if not progress_rows:
        st.info("No saved roadmap yet. Open Flexible Roadmap, enter your topics and generate your learning plan.")
    else:
        total_steps = len(progress_rows)
        done_steps = sum(1 for row in progress_rows if row[6])
        remaining = total_steps - done_steps
        overall_pct = round(done_steps / total_steps * 100)
        c1, c2, c3 = st.columns(3)
        c1.metric("Overall completion", f"{overall_pct}%")
        c2.metric("Completed steps", done_steps)
        c3.metric("Remaining steps", remaining)
        st.progress(overall_pct / 100)
        st.markdown("#### Progress by topic")
        topic_names = list(dict.fromkeys(row[1] for row in progress_rows))
        for topic in topic_names:
            rows_for_topic = [row for row in progress_rows if row[1] == topic]
            topic_done = sum(1 for row in rows_for_topic if row[6])
            topic_pct = round(topic_done / len(rows_for_topic) * 100)
            st.write(f"**{topic}** — {topic_done}/{len(rows_for_topic)} steps · {topic_pct}%")
            st.progress(topic_pct / 100)
        st.markdown("#### Current task status")
        for row in progress_rows:
            status = "Completed" if row[6] else "In progress / pending"
            st.write(f"{'✅' if row[6] else '⬜'} **{row[1]}:** {row[2]} · {status} · Planned: {row[4]}")
        st.caption("Progress is saved in the app database and remains available when you revisit the app, as long as its database storage is persistent.")

st.divider(); st.caption("PlacementPilot AI · Personal learning schedule, saved resume profile and application tracker. Job listings are curated snapshots, not a guarantee of current vacancies. Verify before applying.")
