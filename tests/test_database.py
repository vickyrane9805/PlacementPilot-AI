from src import database


def test_resume_profile_is_saved_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
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
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_profile_db()
    database.save_target_role("Generative AI Engineer")
    assert database.get_profile()[3] == "Generative AI Engineer"


def test_mentor_history_persists_and_can_be_cleared(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_mentor_db()
    database.save_mentor_message("user", "Help me prepare for a RAG interview")
    database.save_mentor_message("assistant", "Let's begin with retrieval fundamentals.")
    history = database.get_mentor_messages()
    assert [row[0] for row in history] == ["user", "assistant"]
    assert "retrieval fundamentals" in history[1][1]
    database.clear_mentor_messages()
    assert database.get_mentor_messages() == []


def test_roadmap_progress_persists_and_updates(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
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
