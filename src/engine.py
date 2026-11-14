import io, re
from collections import OrderedDict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SKILLS = [
    "python","java","c++","sql","machine learning","deep learning","nlp","computer vision","pytorch","tensorflow","scikit-learn","pandas","numpy","fastapi","django","flask","streamlit","rest api","docker","kubernetes","aws","azure","gcp","git","linux","langchain","langgraph","llm","rag","retrieval augmented generation","vector database","embeddings","prompt engineering","hugging face","transformers","agentic ai","postgresql","mongodb","mlops","model deployment","data structures","algorithms","statistics","generative ai","opencv","yolo","fine tuning","evaluation","pytest"
]

ROLE_ROADMAP = {
 "AI Engineer": [
  ("RAG and retrieval", "Build chunking, embedding, retrieval, reranking and grounded answers.", "Document Q&A with citations and retrieval evaluation"),
  ("LLM evaluation", "Measure faithfulness, relevance, latency and cost; add regression tests.", "A small RAG evaluation dashboard"),
  ("Production APIs", "Add authentication, validation, logging, rate limits and async jobs.", "Deploy an AI API with FastAPI and tests"),
  ("MLOps and cloud", "Learn Docker, CI/CD, monitoring and one cloud deployment workflow.", "Containerized app with CI and health checks")],
 "Generative AI Engineer": [
  ("Hugging Face ecosystem", "Understand tokenizers, model loading, pipelines and inference.", "Compare two open models on the same task"),
  ("RAG engineering", "Build ingestion, chunking, vector search, citations and reranking.", "RAG assistant over technical PDFs"),
  ("Agent workflows", "Use tools, state, retries, human approval and guardrails carefully.", "A tool-using research agent with trace logs"),
  ("Evaluation and serving", "Evaluate outputs and optimize latency, cost and reliability.", "LLM benchmark report plus deployed API")],
 "Machine Learning Engineer": [
  ("Core ML practice", "Strengthen feature engineering, validation, leakage checks and metrics.", "End-to-end tabular ML benchmark"),
  ("Deep learning", "Practice PyTorch training loops, regularization and experiment tracking.", "Reproducible model training pipeline"),
  ("Serving", "Package models behind typed APIs and add automated tests.", "FastAPI inference service"),
  ("MLOps", "Add data/model versioning, CI/CD, drift monitoring and retraining.", "Monitored retraining pipeline")],
 "Data Scientist": [
  ("Statistics and experimentation", "Practice hypothesis testing, confidence intervals and A/B tests.", "Experiment analysis notebook"),
  ("SQL and analytics", "Improve joins, window functions, CTEs and query optimization.", "Business analytics case study"),
  ("Modeling", "Compare baselines, tune models and explain feature importance.", "Well-documented predictive model"),
  ("Communication", "Translate findings into clear business recommendations.", "Executive dashboard and concise report")],
 "Computer Vision Engineer": [
  ("Detection fundamentals", "Study IoU, NMS, precision/recall and mAP.", "YOLO evaluation on a custom dataset"),
  ("Data and augmentation", "Build annotation checks, augmentations and reproducible splits.", "Dataset quality and augmentation study"),
  ("Inference optimization", "Profile CPU/GPU inference, batching and ONNX export.", "Latency benchmark with optimized model"),
  ("Deployment", "Serve image/video inference with FastAPI and Docker.", "Containerized CV inference API")],
 "NLP Engineer": [
  ("Transformer foundations", "Understand tokenization, attention, encoder and decoder models.", "Fine-tune a small text classifier"),
  ("Hugging Face", "Practice datasets, tokenizers, Trainer and model evaluation.", "Reproducible NLP fine-tuning project"),
  ("RAG and embeddings", "Build semantic search and measure retrieval quality.", "Semantic search over domain documents"),
  ("Production NLP", "Serve models with batching, monitoring and robust input validation.", "NLP API with tests and Docker")]
}

def extract_text(data: bytes, filename: str) -> str:
    name = filename.lower()
    if name.endswith('.pdf'):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if name.endswith('.docx'):
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    raise ValueError("Please upload a PDF or DOCX file")

def detect_skills(text):
    low = text.lower()
    found = []
    for skill in SKILLS:
        pattern = r'(?<![a-z0-9])' + re.escape(skill) + r'(?![a-z0-9])'
        if re.search(pattern, low): found.append(skill)
    return sorted(set(found))

def analyze_match(resume: str, jd: str):
    vect = TfidfVectorizer(stop_words='english', ngram_range=(1,2), max_features=5000)
    try:
        matrix = vect.fit_transform([resume, jd])
        similarity = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except ValueError: similarity = 0.0
    rs, js = set(detect_skills(resume)), set(detect_skills(jd))
    matched, missing = sorted(rs & js), sorted(js - rs)
    overlap = len(matched) / max(1, len(js))
    score = round(100 * (0.45 * similarity + 0.55 * overlap))
    similarity_pct = round(similarity * 100)
    score = min(100, score)
    reasons = []
    if missing:
        reasons.append(f"Your resume does not explicitly show {len(missing)} listed skill(s): {', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}.")
    if similarity_pct < 20:
        reasons.append("The wording and responsibilities in the job description have limited overlap with your resume.")
    elif similarity_pct < 40:
        reasons.append("Some job-description language overlaps, but several responsibilities may need clearer evidence in your resume.")
    if not matched:
        reasons.append("No direct match was found in the built-in technical-skill vocabulary.")
    if not reasons:
        reasons.append("Your resume shows relevant skill overlap; strengthen the match with specific project outcomes and measurable evidence.")
    actions = []
    if missing: actions.append("Add genuine project or internship evidence for the most important missing skills: " + ", ".join(missing[:5]) + ".")
    actions.append("Rewrite 1–2 project bullets to mirror the role's responsibilities, using measurable outcomes where possible.")
    summary = (f"Good keyword overlap: {len(matched)} listed skill(s) match." if score >= 65 else
               f"Partial fit: {len(matched)} listed skill(s) match, but the resume needs stronger role-specific evidence." if score >= 40 else
               f"Low current fit: only {len(matched)} listed skill(s) match; address the key gaps before applying.")
    return {"score": score, "matched": matched, "missing": missing, "actions": actions,
            "similarity": similarity_pct, "summary": summary, "reasons": reasons}

def build_roadmap(role, current_text):
    current = {s.strip().lower() for s in re.split(r'[,\n]', current_text) if s.strip()}
    roadmap = OrderedDict()
    for i, item in enumerate(ROLE_ROADMAP.get(role, ROLE_ROADMAP['AI Engineer'])):
        skill = item[0]
        status = "Already mentioned" if any(x in skill.lower() or skill.lower() in x for x in current) else "Priority to learn"
        roadmap[f"Phase {i+1} · {status}"] = [item]
    return roadmap

def make_interview_questions(role, jd, resume):
    jd_skills = detect_skills(jd)
    resume_skills = detect_skills(resume)
    focus = [s for s in jd_skills if s in resume_skills][:3]
    gaps = [s for s in jd_skills if s not in resume_skills][:2]
    qs = [f"Explain a project from your experience that is most relevant to a {role} role. What was your contribution and what measurable result did you achieve?",
          "How do you validate that a machine learning model or AI feature is working reliably beyond a single accuracy score?",
          "Describe a technical problem you faced, how you debugged it, and what you learned."]
    qs += [f"Explain how you have used {s} and describe one design decision you made." for s in focus]
    qs += [f"How would you approach learning and implementing {s} for this role?" for s in gaps]
    qs += ["How would you deploy and monitor an AI service used by real users?", "Why are you interested in this role, and what would you aim to deliver in your first 30 days?"]
    return qs[:8]

def evaluate_answer(answer, question, jd):
    words = re.findall(r"[a-zA-Z0-9+#.]+", answer.lower())
    tokens = set(words)
    jd_terms = set(detect_skills(jd))
    overlap = len(tokens & jd_terms)
    structure = min(1.0, len(words)/100)
    specificity = min(1.0, sum(x in answer.lower() for x in ["because", "measured", "result", "trade-off", "metric", "tested", "improved"]) / 3)
    score = round(100 * (0.45*structure + 0.35*specificity + 0.20*min(1, overlap/3)))
    strength = "Your answer has a clear starting point." if len(words)>35 else "You addressed the question, but the answer is quite brief."
    improve = "Use a structured Situation → Task → Action → Result flow. Add the technical choices, trade-offs, and measurable outcome." if score < 75 else "Tighten the explanation and make your personal contribution explicit."
    missing = ", ".join(sorted(jd_terms - tokens)[:5]) or "A concrete metric, test result, or lesson learned"
    return {"score":score,"strength":strength,"improve":improve,"missing":missing}

SKILL_LEARNING_PATHS = {
    "rag": ["Learn embeddings, chunking and document loaders", "Build vector search with FAISS or Chroma", "Add citations, reranking and retrieval evaluation", "Build and deploy a document Q&A project"],
    "langchain": ["Learn chains, prompts and output parsers", "Build a retriever with a vector store", "Add tools and structured outputs", "Test and deploy a small LangChain application"],
    "langgraph": ["Learn graph state, nodes and edges", "Build conditional routing and tool nodes", "Add retries, checkpoints and human approval", "Build a multi-step research or placement agent"],
    "docker": ["Learn images, containers and Dockerfiles", "Containerize a Python API", "Use environment variables, volumes and health checks", "Build and run the project with Docker Compose"],
    "aws": ["Learn IAM, compute, storage and networking basics", "Deploy a small Python API", "Configure logs, secrets and monitoring", "Document a secure cloud deployment"],
    "mlops": ["Learn experiment tracking and reproducibility", "Version data and models", "Build CI tests and a deployment pipeline", "Monitor drift and define retraining triggers"],
    "fastapi": ["Learn routes, request models and response schemas", "Add validation, error handling and authentication", "Write API tests and interactive docs", "Deploy a tested inference API"],
    "hugging face": ["Learn tokenizers, datasets and pipelines", "Load and compare pretrained models", "Fine-tune a small model", "Publish a reproducible model demo"],
    "postgresql": ["Practice SELECT, JOIN, GROUP BY and constraints", "Learn indexes and transactions", "Connect PostgreSQL to a Python API", "Build a persistent application feature"],
    "kubernetes": ["Learn pods, deployments and services", "Write basic YAML manifests", "Deploy an app locally with Minikube or kind", "Add probes, config and rolling updates"],
    "evaluation": ["Define task-specific quality metrics", "Create a representative test set", "Measure accuracy, latency and failure cases", "Build a regression evaluation report"],
    "data structures": ["Practice arrays, strings and hash maps", "Learn stacks, queues, linked lists and trees", "Practice binary search, recursion and heaps", "Solve timed interview problems and review complexity"],
    "algorithms": ["Learn Big-O and common patterns", "Practice two pointers and sliding window", "Practice BFS, DFS, sorting and binary search", "Solve mixed timed problems and explain trade-offs"],
    "linux": ["Practice shell navigation and file operations", "Learn processes, permissions and environment variables", "Use logs, pipes and networking commands", "Automate a project setup or deployment task"],
    "git": ["Practice branches, commits and pull requests", "Resolve merge conflicts", "Use tags and clean commit history", "Collaborate through a reviewed feature branch"],
}

def make_gap_roadmap(missing_skills):
    """Create a skill-by-skill actionable learning plan from detected JD gaps."""
    output = []
    for skill in missing_skills:
        key = skill.lower()
        steps = SKILL_LEARNING_PATHS.get(key)
        if not steps:
            steps = [f"Learn the core concepts and terminology of {skill}",
                     f"Complete a guided hands-on exercise using {skill}",
                     f"Apply {skill} in a small, testable project feature",
                     f"Document what you built and explain key design decisions"]
        output.append({"skill": skill, "steps": steps, "deliverable": f"A portfolio-ready feature demonstrating {skill}"})
    return output


def create_flexible_schedule(items, hours_per_week=8, days_per_week=5, start_date=None):
    """Allocate learning items across selected study days; user can edit/reschedule in UI."""
    from datetime import date, timedelta
    start = start_date or date.today()
    day_slots = [i for i in range(7) if (i % 7) < 7][:]
    # Default weekdays; the caller can supply any chosen weekdays via custom wrapper.
    schedule, day_offset, used_hours = [], 0, 0.0
    daily_hours = max(0.5, float(hours_per_week) / max(1, int(days_per_week)))
    for item in items:
        schedule.append({"date": start + timedelta(days=day_offset), "title": item, "hours": min(daily_hours, 2.0)})
        day_offset += 1
    return schedule


def parse_roadmap_topics(raw_text):
    """Parse comma/newline/semicolon/bulleted input without inventing extra topics."""
    if isinstance(raw_text, str):
        values = re.split(r"[,;\n]+", raw_text)
    else:
        values = raw_text or []
    cleaned, seen = [], set()
    for value in values:
        topic = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s*", "", str(value)).strip()
        normalized = re.sub(r"\s+", " ", topic).casefold()
        if topic and normalized not in seen:
            cleaned.append(topic)
            seen.add(normalized)
    return cleaned


def build_topic_roadmap(topics):
    """Create actionable steps only for the exact topics explicitly entered by the user."""
    plans = []
    for topic in parse_roadmap_topics(topics):
        key = topic.casefold()
        aliases = {"huggingface": "hugging face", "hf transformers": "hugging face",
                   "retrieval augmented generation": "rag", "data structures and algorithms": "data structures"}
        key = aliases.get(key, key)
        known = SKILL_LEARNING_PATHS.get(key)
        if known is None:
            known_key = next((k for k in SKILL_LEARNING_PATHS if k in key or key in k), None)
            known = SKILL_LEARNING_PATHS.get(known_key) if known_key else None
        steps = list(known) if known else [
            f"Learn the fundamentals, terminology and core concepts of {topic}",
            f"Complete guided exercises and solve at least 3 small problems using {topic}",
            f"Build a practical mini-project that uses {topic} to solve one clear problem",
            f"Test the project, document decisions and explain what you learned about {topic}",
        ]
        plans.append({'topic': topic, 'steps': steps,
                      'deliverable': f"A portfolio-ready mini-project demonstrating {topic}"})
    return plans
