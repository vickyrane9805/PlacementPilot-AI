"""Live remote technology-job feed powered by Remotive's public API.

Remotive asks API consumers to cache responses, link to each original listing,
credit Remotive, and keep request frequency low. The UI caches the feed for 6h.
"""
from datetime import datetime
import requests

API_URL = "https://remotive.com/api/remote-jobs"
AI_TERMS = (
    "artificial intelligence", "machine learning", "deep learning", "generative ai",
    "genai", "llm", "large language model", "nlp", "computer vision", "data scientist",
    "data science", "python developer", "ai engineer", "ml engineer", "research engineer",
    "prompt engineer", "rag", "agentic", "robotics"
)

def fetch_remote_tech_jobs(limit=500, timeout=15):
    """Fetch currently active remote listings; caller should cache for at least 6h."""
    response = requests.get(API_URL, params={"limit": int(limit)}, timeout=timeout,
                            headers={"User-Agent": "PlacementPilotAI/1.0"})
    response.raise_for_status()
    payload = response.json()
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    results = []
    for job in jobs:
        title = str(job.get("title") or "").strip()
        description = str(job.get("description") or "")
        category = str(job.get("category") or "")
        searchable = f"{title} {category} {description}".lower()
        if not any(term in searchable for term in AI_TERMS):
            continue
        job_type = str(job.get("job_type") or "Not specified").replace("_", " ").title()
        results.append({
            "company": str(job.get("company_name") or "Company not listed"),
            "role": title or "Role not listed",
            "type": job_type,
            "location": str(job.get("candidate_required_location") or "Remote; check country eligibility"),
            "mode": "Remote",
            "fit": f"Remote technology role · {category or 'Technology'}",
            "eligibility": str(job.get("candidate_required_location") or "Check eligible countries on employer listing"),
            "duration": job_type,
            "pay": str(job.get("salary") or "Not stated"),
            "url": str(job.get("url") or "https://remotive.com/remote-jobs"),
            "source": "Remotive (public feed; listings may be delayed by up to 24 hours)",
            "published": str(job.get("publication_date") or ""),
            "description": description,
            "live": True,
        })
    results.sort(key=lambda x: x.get("published", ""), reverse=True)
    return results
