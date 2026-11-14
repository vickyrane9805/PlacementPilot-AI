import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "placementpilot.db"
logger = logging.getLogger(__name__)


@contextmanager
def connect():
    """Open a SQLite connection and back up every committed write to private Blob."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=30)
    before_changes = con.total_changes
    changed = False
    try:
        yield con
        changed = con.total_changes > before_changes
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

    # Local commits remain successful even if the backup provider is temporarily
    # unavailable. The app logs the failure; the UI also exposes backup status.
    if changed:
        try:
            from src.blob_backup import get_blob_token, backup_database
            if get_blob_token():
                backup_database(DB_PATH)
        except Exception:
            logger.exception(
                "SQLite data was saved locally, but its Vercel Blob backup failed. "
                "Check BLOB_READ_WRITE_TOKEN and Blob usage."
            )

def init_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT NOT NULL, role TEXT NOT NULL,
            location TEXT, applied_on TEXT, status TEXT, url TEXT, notes TEXT)''')

def add_application(company, role, location, applied_on, status, url, notes):
    with connect() as con:
        con.execute("INSERT INTO applications(company,role,location,applied_on,status,url,notes) VALUES(?,?,?,?,?,?,?)", (company,role,location,applied_on,status,url,notes))

def get_applications():
    with connect() as con:
        return con.execute("SELECT id,company,role,location,applied_on,status,url,notes FROM applications ORDER BY applied_on DESC, id DESC").fetchall()

def update_application(app_id, status):
    with connect() as con:
        con.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))

def delete_application(app_id):
    with connect() as con:
        con.execute("DELETE FROM applications WHERE id=?", (app_id,))

# Day planner persistence

def init_planner_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS planner_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_date TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'Learning',
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            notes TEXT DEFAULT '',
            completed INTEGER NOT NULL DEFAULT 0
        )''')

def add_planner_task(task_date, title, category, duration_minutes, notes=''):
    with connect() as con:
        con.execute('INSERT INTO planner_tasks(task_date,title,category,duration_minutes,notes) VALUES(?,?,?,?,?)',
                    (task_date, title, category, duration_minutes, notes))

def get_planner_tasks(task_date):
    with connect() as con:
        return con.execute('SELECT id,task_date,title,category,duration_minutes,notes,completed FROM planner_tasks WHERE task_date=? ORDER BY completed, id', (task_date,)).fetchall()

def set_planner_task_done(task_id, completed):
    with connect() as con:
        con.execute('UPDATE planner_tasks SET completed=? WHERE id=?', (1 if completed else 0, task_id))

def delete_planner_task(task_id):
    with connect() as con:
        con.execute('DELETE FROM planner_tasks WHERE id=?', (task_id,))

def update_planner_task(task_id, task_date, duration_minutes):
    with connect() as con:
        con.execute('UPDATE planner_tasks SET task_date=?, duration_minutes=? WHERE id=?',
                    (task_date, duration_minutes, task_id))

# Persistent candidate profile and parsed resume (never store the original file by default).
def init_profile_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS candidate_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            resume_name TEXT NOT NULL DEFAULT '',
            resume_text TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            target_role TEXT NOT NULL DEFAULT 'AI Engineer'
        )''')

def save_resume(resume_name, resume_text):
    with connect() as con:
        con.execute('''INSERT INTO candidate_profile(id,resume_name,resume_text,updated_at)
            VALUES(1,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET resume_name=excluded.resume_name,
            resume_text=excluded.resume_text,updated_at=CURRENT_TIMESTAMP''', (resume_name, resume_text))

def get_profile():
    with connect() as con:
        return con.execute('SELECT resume_name,resume_text,updated_at,target_role FROM candidate_profile WHERE id=1').fetchone()

def save_target_role(role):
    with connect() as con:
        con.execute('''INSERT INTO candidate_profile(id,target_role) VALUES(1,?)
            ON CONFLICT(id) DO UPDATE SET target_role=excluded.target_role''', (role,))

def get_application_stats():
    with connect() as con:
        return con.execute('SELECT status, COUNT(*) FROM applications GROUP BY status').fetchall()

def get_task_stats(start_date, end_date):
    with connect() as con:
        return con.execute('''SELECT COUNT(*), SUM(completed), SUM(duration_minutes),
            SUM(CASE WHEN completed=1 THEN duration_minutes ELSE 0 END)
            FROM planner_tasks WHERE task_date BETWEEN ? AND ?''', (start_date, end_date)).fetchone()


# Persistent AI mentor conversation history (API keys are never stored here).
def init_mentor_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS mentor_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')

def save_mentor_message(role, content):
    if role not in ('user', 'assistant'):
        raise ValueError("role must be user or assistant")
    with connect() as con:
        con.execute('INSERT INTO mentor_messages(role,content) VALUES(?,?)', (role, content))
        # Keep the latest 100 messages to avoid unbounded local database growth.
        con.execute('DELETE FROM mentor_messages WHERE id NOT IN (SELECT id FROM mentor_messages ORDER BY id DESC LIMIT 100)')

def get_mentor_messages(limit=40):
    with connect() as con:
        rows = con.execute('SELECT role,content,created_at FROM mentor_messages ORDER BY id DESC LIMIT ?', (int(limit),)).fetchall()
    return list(reversed(rows))

def clear_mentor_messages():
    with connect() as con:
        con.execute('DELETE FROM mentor_messages')

# Persistent custom learning roadmap and progress tracking
def init_roadmap_db():
    with connect() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS roadmap_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            step TEXT NOT NULL,
            deliverable TEXT NOT NULL DEFAULT '',
            planned_date TEXT NOT NULL,
            hours REAL NOT NULL DEFAULT 1.0,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')

def replace_roadmap_steps(items):
    """Replace the active custom roadmap with a newly generated one."""
    with connect() as con:
        con.execute('DELETE FROM roadmap_steps')
        con.executemany(
            'INSERT INTO roadmap_steps(topic,step,deliverable,planned_date,hours) VALUES(?,?,?,?,?)',
            [(x['topic'], x['step'], x.get('deliverable',''), x['date'], float(x.get('hours',1.0))) for x in items]
        )

def get_roadmap_steps():
    with connect() as con:
        return con.execute('''SELECT id,topic,step,deliverable,planned_date,hours,completed
            FROM roadmap_steps ORDER BY topic, id''').fetchall()

def set_roadmap_step_done(step_id, completed):
    with connect() as con:
        con.execute('UPDATE roadmap_steps SET completed=? WHERE id=?', (1 if completed else 0, step_id))
