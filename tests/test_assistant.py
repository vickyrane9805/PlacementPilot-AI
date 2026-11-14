from src.assistant import build_system_prompt


def test_system_prompt_uses_candidate_context_and_truthfulness_rules():
    prompt = build_system_prompt({
        "target_role": "Generative AI Engineer",
        "resume_name": "resume.pdf",
        "resume_text": "Python, LangGraph, RAG",
        "application_summary": "Acme: GenAI Intern (Applied)",
        "planner_summary": "Practice RAG evaluation (pending, 60 min)",
    })
    assert "Generative AI Engineer" in prompt
    assert "LangGraph" in prompt
    assert "Acme" in prompt
    assert "NEVER invent" in prompt


def test_system_prompt_handles_missing_profile():
    prompt = build_system_prompt({})
    assert "No resume saved yet" in prompt
    assert "AI Engineer" in prompt
