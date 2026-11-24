import os
import pytest
from src import database

@pytest.fixture(autouse=True)
def isolated_database(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to a disposable PostgreSQL database')
    if url == os.environ.get('DATABASE_URL'):
        pytest.fail('Test database must be separate from production')
    monkeypatch.setenv('DATABASE_URL', url)
    database.initialize_database()
    with database.connect() as con:
        con.execute('TRUNCATE applications, planner_tasks, candidate_profile, mentor_messages, roadmap_steps, workspace_state RESTART IDENTITY')



def test_resume_profile_is_saved_and_reused(tmp_path, monkeypatch):
    database.init_profile_db()
    database.save_resume("candidate.pdf", "Python, PyTorch and RAG experience")
    profile = database.get_profile()
    assert profile[0] == "candidate.pdf"
    assert "PyTorch" in profile[1]
    database.save_resume("updated.pdf", "Python and FastAPI")
    updated = database.get_profile()
    assert updated[0] == "updated.pdf"
    assert updated[1] == "Python and FastAPI"


def test_target_role_persists_without_resume(tmp_path, monkeypatch):
    database.init_profile_db()
    database.save_target_role("Generative AI Engineer")
    assert database.get_profile()[3] == "Generative AI Engineer"


def test_mentor_history_persists_and_can_be_cleared(tmp_path, monkeypatch):
    database.init_mentor_db()
    database.save_mentor_message("user", "Help me prepare for a RAG interview")
    database.save_mentor_message("assistant", "Let's begin with retrieval fundamentals.")
    history = database.get_mentor_messages()
    assert [row[0] for row in history] == ["user", "assistant"]
    assert "retrieval fundamentals" in history[1][1]
    database.clear_mentor_messages()
    assert database.get_mentor_messages() == []


def test_roadmap_progress_persists_and_updates(tmp_path, monkeypatch):
    database.init_roadmap_db()
    database.replace_roadmap_steps([
        {"topic": "RAG", "step": "Learn chunking", "deliverable": "RAG demo", "date": "2026-11-12", "hours": 1.5},
        {"topic": "RAG", "step": "Build retrieval", "deliverable": "RAG demo", "date": "2026-11-13", "hours": 2},
    ])
    rows = database.get_roadmap_steps()
    assert len(rows) == 2
    database.set_roadmap_step_done(rows[0][0], True)
    updated = database.get_roadmap_steps()
    assert updated[0][6] == 1
    assert updated[1][6] == 0

def test_workspace_state():
    database.save_workspace_state('questions', ['Question 1'])
    database.save_workspace_state('answer_idx', 0)
    assert database.get_workspace_state() == {'questions':['Question 1'], 'answer_idx':0}

def test_application_and_planner():
    database.add_application('Example','Engineer','Pune','2026-11-25','Applied','','')
    row = database.get_applications()[0]
    database.update_application(row[0], 'Interview')
    assert database.get_applications()[0][5] == 'Interview'
    database.add_planner_task('2026-11-25','Learn SQL','Learning',60)
    task = database.get_planner_tasks('2026-11-25')[0]
    database.set_planner_task_done(task[0], True)
    assert database.get_task_stats('2026-11-25','2026-11-25') == (1,1,60,60)
