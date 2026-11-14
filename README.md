# PlacementPilot AI

A placement preparation workspace for AI/ML/GenAI candidates. It combines resume/JD matching, flexible skill roadmaps, a persistent day planner, curated opportunity discovery, interview practice, and an application tracker.

## Features
- PDF/DOCX resume text extraction; parsed resume text and filename are stored in the app database and automatically reused on later visits (no external AI API call)
- Transparent hybrid matching: TF-IDF cosine similarity + skill overlap
- Skill-gap learning paths generated from missing JD skills, with step-by-step topics and portfolio deliverables
- Flexible roadmap scheduling: weekly study-hour budget, chosen study days, start date, editable task dates and durations
- Persistent day planner: add, complete, delete and organize tasks by date and category (learning, DSA, project, applications, interview prep, revision)
- Curated Pune/India job and internship board plus a live remote AI/ML feed from Remotive; listings include posting dates, original apply links, source attribution, and one-click save to the application tracker
- Short job-match explanation showing why a role is a weak/partial/strong fit, missing skills, and practical next steps
- Interview question generation and rule-based answer feedback (AI Mentor can provide deeper coaching)
- SQLite application, planner and recent AI mentor conversation tracking (API keys are never stored in SQLite)
- Context-aware AI placement mentor: resume audit, skill-gap coaching, technical debugging, project review, interview practice, application kit and weekly review
- Guided 14-day placement sprint, persistent recent chat history, and a confirm-before-adding AI recommendation to the day planner
- OpenAI or Groq support through an OpenAI-compatible API client; user consent is required before sending resume/chat context

## Run locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## Job-search data
The Pune/India employer listings are a curated snapshot and may become outdated. The Jobs & Internships tab also fetches a live remote AI/ML feed from Remotive's public API when the app session loads. The response is cached for six hours to respect Remotive's request guidance; Remotive says listings may be delayed by up to 24 hours. Each listing links back to its original Remotive page and credits Remotive as the source. The feed is remote-focused and does not replace India/Pune local searches. Always verify vacancy status, country eligibility, compensation and application requirements on the original employer page. See [Remotive API documentation](https://github.com/remotive-com/remote-jobs-api) and follow its terms.

## Enable the AI Mentor

The AI Mentor supports OpenAI and Groq. To use the Groq free tier, open **AI Mentor**, select **Groq**, enter your Groq API key and model `openai/gpt-oss-20b`, and tick the consent checkbox. The key is held only in the current app session and is not written to SQLite. Recent mentor messages are stored locally so the conversation can be resumed.

For local development, copy `.env.example` to `.env` and set your Groq key. For example:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

Or use Groq:

```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Install dependencies and restart Streamlit after changing `.env`. The project default was set to `openai/gpt-oss-20b`; model availability and free-tier limits can change, so verify the current model list in Groq documentation. On Streamlit Community Cloud, add the corresponding values under **App settings → Secrets** (TOML format), for example:

```toml
OPENAI_API_KEY = "your_key_here"
OPENAI_MODEL = "gpt-4o-mini"
```

Never commit `.env`, `secrets.toml`, API keys or your resume. When you send a mentor prompt with consent enabled, the saved resume text and recent conversation are sent to the selected provider so it can personalize its answer. Review that provider's privacy and retention terms. Usage may incur provider charges and is subject to its rate limits.

## Custom learning roadmap and progress tracking
- Enter any topics you want to learn in Flexible Roadmap (comma-separated, semicolon-separated, one per line, or as a bulleted list); the generated plan uses only those topics and removes duplicate entries.
- Known topics such as RAG, LangChain, Docker, Hugging Face and DSA receive topic-specific steps. Other topics receive a practical four-step learning path and a project deliverable.
- Mark each roadmap step complete in Flexible Roadmap. The separate Progress tab shows overall and per-topic completion.
- Roadmap steps and completion status are stored in SQLite alongside the other app data.

## Deploy on Streamlit Community Cloud
1. Create a GitHub repository and push this project (do not commit your resume or secrets).
2. Open https://share.streamlit.io/ and connect GitHub.
3. Select the repository, branch, and `app.py` as the main file.
4. Deploy. The core workspace works without an AI key. To enable the AI Mentor, add an OpenAI or Groq API key as described below.

**Persistence:** The app continues to use one SQLite file, `data/placementpilot.db`. Streamlit Community Cloud's local filesystem is ephemeral, so configure the private Vercel Blob backup described below before relying on hosted data. The app restores the newest valid remote snapshot once when the Streamlit server process starts and uploads a new validated snapshot after each committed database write. Blob failures do not undo local commits; check the Streamlit logs and Blob status if an upload fails. Keep a separate offline backup as well. Do not commit the database or upload resumes to a public repository.


## Persistent SQLite backups with private Vercel Blob

The application still uses SQLite and the same `data/placementpilot.db` file. Vercel Blob stores private, timestamped backup snapshots; it is not used as a live database.

1. Create a **Private** Vercel Blob store and copy its `BLOB_READ_WRITE_TOKEN`.
2. In Streamlit Community Cloud, open your app's **Settings → Secrets** and add:

   ```toml
   BLOB_READ_WRITE_TOKEN = "your_vercel_read_write_token"
   ```

3. Redeploy the app so the `vercel-blob` dependency is installed and the secret is available.
4. To seed the cloud store with an existing database from your laptop, use PowerShell from the project root:

   ```powershell
   $env:BLOB_READ_WRITE_TOKEN="your_vercel_read_write_token"
   python -m pip install -r requirements.txt
   python scripts/seed_database_to_blob.py --db "C:\\path\\to\\your\\data\\placementpilot.db"
   ```

5. On the next Streamlit server start, the newest valid private backup is restored before database tables are initialized. Each committed write then creates a new snapshot. The app retains the newest 20 snapshots.

The token must never be committed to GitHub. Use a **private** Blob store because the database can contain parsed resume text and application history. If Blob is unavailable, the app keeps the local SQLite commit and logs the backup failure; it does not falsely report a successful cloud backup. Keep an independent copy of the database too.

### Job feed refresh

The Jobs & Internships page has a **Refresh live jobs** button. It clears the six-hour cache and requests the Remotive remote AI/ML feed again. The curated Pune/India opportunities above are a static snapshot and are not refreshed by this button. A refresh can only show new companies when Remotive has published new listings. Remotive recommends caching and limiting request frequency; avoid repeatedly clicking the button.

## Docker

```bash
docker build -t placementpilot-ai .
docker run --rm -p 8501:8501 placementpilot-ai
```

## Project structure

```text
placementpilot/
├── app.py
├── src/
│   ├── assistant.py
│   ├── engine.py
│   ├── database.py
│   └── opportunities.py
├── data/                 # local SQLite DB; ignored by git
├── tests/
├── requirements.txt
├── Dockerfile
└── README.md
```

## Important limitations
- Match percentage is a heuristic, not an ATS score or hiring probability.
- Skill detection uses a built-in vocabulary and can miss synonyms or specialized requirements.
- The Pune/India job list is curated; the separate remote AI/ML feed is fetched from Remotive and cached for six hours. Remote-feed coverage and listing freshness depend on Remotive.
- Interview feedback is rule-based and does not deeply validate technical correctness.
- The original resume file is not stored; only extracted text and its filename are saved in SQLite. Treat the parsed text as personal data and use a private deployment. The built-in resume score is a heuristic, not an ATS score or hiring prediction.

## Recommended production upgrades
1. Add authentication and managed PostgreSQL.
2. Add additional verified India-focused job sources and employer-board integrations.
3. Add structured AI actions that can create planner tasks directly, with user confirmation.
4. Add CI/CD, analytics, logging, monitoring and scheduled job-feed refresh.
