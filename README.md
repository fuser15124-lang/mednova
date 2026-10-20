# MedNova AI — Streamlit Community Cloud starter

This repository includes a Streamlit UI (`streamlit_app.py`) and the original FastAPI API (`app/main.py`). For the simplest Streamlit deployment, choose `streamlit_app.py` as the app entry point.

## Features in the Streamlit interface
- Email/password registration and sign-in with salted scrypt password hashes.
- Per-user saved conversations using the included SQLAlchemy models.
- AI chat through an OpenAI-compatible chat-completions API (Groq is supported).
- PubMed search using NCBI E-utilities.
- Text extraction from PDF and UTF-8 TXT documents.
- English and Persian UI labels, with language selection.
- Medical-information disclaimer and honest error handling when AI is not configured.

## Deploy to Streamlit Community Cloud
1. Push this repository to GitHub.
2. Go to https://share.streamlit.io/ and choose **Create app**.
3. Select the repository/branch and set **Main file path** to `streamlit_app.py`.
4. Open **Advanced settings / Secrets** and add secrets similar to:

```toml
AI_BASE_URL = "https://api.groq.com/openai/v1"
AI_API_KEY = "paste-your-new-rotated-key-here"
AI_MODEL = "a-supported-model-name"
JWT_SECRET = "replace-with-a-long-random-secret"
DATABASE_URL = "sqlite:///./mednova.db"
MAX_UPLOAD_MB = "10"
```

Use a newly rotated API key. Never commit keys to GitHub or put them in frontend/static files. Confirm the selected model is available to your provider account. For Groq, consult its current model list.

5. Click **Deploy** and wait for the app to start.

## Important limitations
- Streamlit Community Cloud has resource/sleep limitations and is not a production hosting guarantee.
- SQLite storage on a hosted app may not be durable across rebuilds/redeploys. For persistent accounts and history, configure a managed PostgreSQL database and set `DATABASE_URL` to its connection URL. Do not use a local SQLite file as the only production database.
- This starter does not include email verification, password reset, MFA, clinician credential verification, malware scanning, OCR for scanned PDFs, or clinical validation.
- Do not upload identifiable patient data. The app is educational, not a diagnostic tool, and AI outputs may be inaccurate.
- Professional access is deliberately disabled until a real verification workflow is implemented.
- The existing FastAPI backend remains in `app/main.py`; Streamlit can run without deploying that HTTP server because the Streamlit UI calls the shared Python functions directly.

## Local run (Windows)
```powershell
py -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

To run the original FastAPI API instead:
```powershell
uvicorn app.main:app --reload
```
