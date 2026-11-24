# PlacementPilot AI — Supabase edition

Single-user Streamlit workspace. Existing resume matching, planner, applications, roadmap, job feeds, interview and mentor features use direct PostgreSQL persistence for saved records. No Vercel token or local database is needed. Generated match results, gap roadmap and interview questions/current question are also persisted. Unsubmitted form drafts and interview answer evaluations remain temporary. Mentor history retains the latest 100 messages, as in the original app.

## Free deployment
1. Create a free project at https://supabase.com/dashboard. Save the database password securely. Wait for provisioning.
2. In the project click Connect, choose **Session pooler** (port 5432, IPv4-compatible), and copy the PostgreSQL URI. Replace the password placeholder with your URL-encoded database password. Do not use the anon API key. No SQL setup is needed: the app creates its own `placementpilot` schema and tables.
3. Create a GitHub repository and upload the contents of this folder, including `src`, `app.py`, `requirements.txt`, and `.streamlit/config.toml`. Never upload `.env`, secrets or old database snapshots. A new repository avoids leaving obsolete Blob code behind.
4. Go to https://share.streamlit.io and deploy the repository, branch main, entrypoint app.py. Choose Python 3.11 or 3.12 if offered. In Advanced settings / Secrets paste:

```toml
DATABASE_URL = "postgresql://postgres.PROJECT_REF:ENCODED_PASSWORD@POOLER_HOST:5432/postgres"
APP_PASSWORD = "your-long-unique-workspace-password"
GROQ_API_KEY = "your-existing-key"
GROQ_MODEL = "openai/gpt-oss-20b"
```

Use the actual URI from Supabase, not the example. Groq settings are optional for non-mentor features. Keep the Streamlit app private if possible; the app also requires a workspace password. This is one shared workspace, not multi-user authentication. Do not share the password. Free quotas and inactivity policies apply; check https://supabase.com/pricing. If paused, restore the project in Supabase. No paid add-ons are needed.

## Local Windows setup
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env` with the real credentials, then `streamlit run app.py`.

## Recover previous data (optional, before entering new data)
Download old `.db` snapshots from Vercel Blob; keep independent copies. Choose a snapshot with actual records, not simply the newest. With local environment configured to the new Supabase database:
```powershell
python -m scripts.migrate_sqlite "C:\path\old.db"
python -m scripts.migrate_sqlite "C:\path\old.db" --apply
```
The first command previews record counts and checks SQLite integrity. The second imports all available original tables in a single transaction, preserves IDs and adjusts sequences. It refuses a nonempty destination. Stop the old app before migration and avoid concurrent use. Existing session-only data cannot be recovered from SQLite. Keep the old backups until verified.

## Verify persistence
Sign in, upload a resume, add an application and planner task, mark a roadmap step complete, generate interview questions. Check Supabase Table Editor (select placementpilot schema). Reboot the Streamlit app from its management menu, sign in again and verify records. If connection fails the app stops rather than creating a blank local database. Database write errors are not treated as successful writes. Export data periodically using Supabase/PostgreSQL tools; free service is not a substitute for independent backups.

## Tests
`python -m pytest` runs unit tests (install pytest separately). Database integration tests require `TEST_DATABASE_URL` pointing to a dedicated disposable PostgreSQL database; they truncate the workspace tables. Never use production credentials for tests.
