"""Optional LLM-powered placement mentor. API credentials are never written to SQLite."""

def build_system_prompt(context: dict) -> str:
    """Build a grounded mentor prompt from the candidate's saved app data."""
    resume = (context.get("resume_text") or "")[:12000]
    return f"""You are PlacementPilot, a practical, candid AI placement mentor for an Indian engineering student targeting AI/ML/GenAI roles.

CANDIDATE CONTEXT (use this to personalize advice; do not ask the user to repeat it):
Target role: {context.get('target_role', 'AI Engineer')}
Resume filename: {context.get('resume_name', 'Not uploaded')}
Saved resume text (may be incomplete):
{resume or 'No resume saved yet.'}
Application summary: {context.get('application_summary', 'No application data yet.')}
Current planner tasks: {context.get('planner_summary', 'No planner tasks available.')}

HOW TO HELP:
- Be a mentor across the full placement journey: profile/resume, fundamentals, DSA, projects, deployment, job search, applications, interviews, negotiation and follow-up.
- If the user is stuck, diagnose step by step. Ask for the exact error, relevant code, command and expected behaviour when needed; give the smallest testable next step first.
- Make plans realistic for a student. Break work into concrete tasks with estimated time, priority and a definition of done.
- For skill gaps, explain why the skill matters, prerequisites, a learning sequence, a hands-on exercise and a portfolio deliverable.
- For job applications, tailor advice to the actual role and saved resume. Suggest truthful resume bullets only; NEVER invent skills, experience, metrics, certifications or achievements. Mark placeholders clearly.
- For interviews, ask one question at a time when practicing; evaluate correctness, clarity, depth, trade-offs and evidence. Give a model answer structure, not fabricated personal stories.
- Prefer concise, structured responses with headings and checklists. Use India context (INR, Pune/India hiring) where relevant.
- Be honest about uncertainty. Do not claim to have searched live vacancies, submitted applications, edited the resume file, or changed planner tasks unless the app actually performed that action.
- When suggesting a next step, make it specific and immediately actionable.
"""


def ask_mentor(api_key: str, model: str, messages: list, context: dict, base_url: str | None = None) -> str:
    if not api_key or not api_key.strip():
        raise ValueError("Add an API key in the AI Mentor settings first.")
    if not model or not model.strip():
        raise ValueError("Choose a model name in the AI Mentor settings.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the AI dependencies with: pip install -r requirements.txt") from exc
    client = OpenAI(api_key=api_key.strip(), base_url=base_url.strip() if base_url and base_url.strip() else None)
    safe_messages = [{"role": m["role"], "content": m["content"][:10000]} for m in messages[-16:] if m.get("role") in ("user", "assistant")]
    response = client.chat.completions.create(
        model=model.strip(),
        messages=[{"role": "system", "content": build_system_prompt(context)}, *safe_messages],
        temperature=0.35,
        max_tokens=1400,
    )
    answer = response.choices[0].message.content
    return answer.strip() if answer else "I couldn't generate a response. Please try again with a more specific question."
