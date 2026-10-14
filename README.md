# Resume Reviewer (CSC 603 Team 16 Capstone)

Web app that scans a resume, scores it for ATS compatibility, compares it against a job description, and uses an LLM to suggest grounded rewrites.

> Project name is a placeholder until the team picks one.

## Team

| Name | Role |
| --- | --- |
| Dylan | Team lead, full stack |
| Ajmaluddin | TBD |
| John | TBD |
| Emma | TBD |

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | HTML, CSS, vanilla JavaScript (no build step) |
| Backend | Python 3.11+, FastAPI |
| LLM | `openai/gpt-oss-120b` via Groq API |
| Parsing | pdfplumber, python-docx |
| Similarity | Sentence Transformers (`all-MiniLM-L6-v2`) |
| Database | PostgreSQL 16 |

## Repo layout

```
backend/
  app/
    main.py          FastAPI app, router registration
    config.py        Settings loaded from .env
    db.py            Database connection
    routers/         One file per API area (auth, resumes, analyses, revisions)
    services/        Core logic: parser, ATS scorer, match scorer, LLM, grounding
    schemas.py       Pydantic request/response models
  tests/             pytest tests
  requirements.txt
db/
  schema.sql         PostgreSQL tables
frontend/
  index.html
  css/
  js/
docs/                Report, diagrams, meeting notes
```

## Local setup

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 16 installed locally ([download](https://www.postgresql.org/download/); macOS: `brew install postgresql@16`)
- A Groq API key from https://console.groq.com

### 2. Environment

```bash
cp .env.example .env
# Fill in GROQ_API_KEY and SECRET_KEY
```

Never commit `.env`. It is already in `.gitignore`.

### 3. Database

With PostgreSQL running, create the user, database, and tables (one time):

```bash
psql -U postgres -c "CREATE USER resume WITH PASSWORD 'resume';"
psql -U postgres -c "CREATE DATABASE resume_reviewer OWNER resume;"
psql -U resume -d resume_reviewer -f db/schema.sql
```

On macOS with Homebrew, use your system username instead of `postgres` for the first two commands. If you change the user or password, update `DATABASE_URL` in `.env`.

To reset the tables later, rerun the last command (the schema uses `IF NOT EXISTS`, so drop tables first if you need a clean slate).

### 4. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

API runs at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

### 5. Frontend

```bash
cd frontend
python -m http.server 5500
```

Open http://localhost:5500.

### 6. Tests and lint

```bash
cd backend
pytest
ruff check .
```

## Workflow

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching, commits, and pull requests.

## Milestones

| Week | Dates (2026) | Milestone |
| --- | --- | --- |
| 1 | Oct 19 to 25 | Requirements, repo setup, DB schema, API contract |
| 2 | Oct 26 to Nov 1 | Accounts and auth, frontend pages |
| 3 | Nov 2 to 8 | Resume upload and parsing |
| 4 | Nov 9 to 15 | ATS scorer, job description extraction |
| 5 | Nov 16 to 22 | Match score, test set |
| 6 | Nov 23 to 29 | Reviser, grounding check, accept/reject |
| 7 | Nov 30 to Dec 6 | History, export, evaluation, bug fixes |
| 8 | Dec 7 to 13 | Final report, slides, demo |
