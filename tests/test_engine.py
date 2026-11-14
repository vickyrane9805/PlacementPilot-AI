from src.engine import analyze_match, detect_skills, evaluate_answer

def test_skill_detection():
    assert "python" in detect_skills("Built APIs in Python and FastAPI")

def test_match_score_range():
    result = analyze_match("Python, SQL, FastAPI", "Need Python, SQL, Docker and FastAPI")
    assert 0 <= result["score"] <= 100
    assert "docker" in result["missing"]

def test_answer_feedback():
    result = evaluate_answer("I tested the model and improved recall. The result was measured on a held-out dataset.", "How did you test?", "Python ML")
    assert 0 <= result["score"] <= 100


def test_gap_roadmap_has_actionable_steps():
    from src.engine import make_gap_roadmap
    roadmap = make_gap_roadmap(["rag", "docker"])
    assert len(roadmap) == 2
    assert all(len(item["steps"]) >= 3 for item in roadmap)
    assert all(item["deliverable"] for item in roadmap)


def test_custom_roadmap_uses_only_user_entered_topics():
    from src.engine import build_topic_roadmap
    plans = build_topic_roadmap(["Hugging Face", "My Custom Topic"])
    assert [p["topic"] for p in plans] == ["Hugging Face", "My Custom Topic"]
    assert any("tokenizers" in step.lower() for step in plans[0]["steps"])
    assert all("My Custom Topic" in step for step in plans[1]["steps"])


def test_match_explains_why_a_resume_is_not_a_strong_match():
    result = analyze_match("Python and pandas projects", "Need Python, Docker, Kubernetes and AWS")
    assert result["summary"]
    assert result["reasons"]
    assert any("docker" in reason.lower() or "kubernetes" in reason.lower() for reason in result["reasons"])


def test_roadmap_topic_parser_handles_bullets_and_duplicates():
    from src.engine import parse_roadmap_topics, build_topic_roadmap
    topics = parse_roadmap_topics("- RAG\n2. Docker, rag; Hugging Face")
    assert topics == ["RAG", "Docker", "Hugging Face"]
    plans = build_topic_roadmap(topics)
    assert [p["topic"] for p in plans] == topics
    assert all(len(p["steps"]) >= 4 for p in plans)
