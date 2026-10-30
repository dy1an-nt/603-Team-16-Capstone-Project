# Resume Reviewer (CSC 603 Team 16 Capstone)

Web app that scans a resume, scores it for ATS compatibility, compares it against a job description, and uses an LLM to suggest grounded rewrites.

> Project name is a placeholder until the team picks one.

## Team

| Name | Role |
| --- | --- |
| Dylan | Team lead, full stack |
| Ajmaluddin | Backend |
| John | Frontend |
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
scripts/
  py.mjs             Runs backend/.venv Python for the npm scripts
package.json         npm scripts (no npm packages)
```

## Local setup

### 1. Prerequisites

- Python 3.11+
- Node.js 18+ (for the `npm run` shortcuts below; no npm packages are installed)
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

From the repo root, install once, then start the API:

```bash
npm run setup
npm run backend
```

`npm run setup` creates `backend/.venv` and installs `requirements.txt` and `requirements-dev.txt` into it. Rerun it after pulling a change to either file. The npm scripts use that venv directly, so you never need to activate it.

API runs at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

### 5. Frontend

In a second terminal:

```bash
npm run frontend
```

Open http://localhost:5500.

### 6. Tests and lint

```bash
npm run check
```

That runs `npm run lint` (ruff) and then `npm test` (pytest). Arguments after `--` go to pytest, e.g. `npm test -- -k auth`.

The database tests in `tests/test_repositories.py` are skipped unless `TEST_DATABASE_URL` points at a throwaway database. CI always runs them. To run them locally, create the test database once:

```bash
psql -U postgres -c "CREATE DATABASE resume_reviewer_test OWNER resume;"
```

Then run the tests with the URL set (change the port if your PostgreSQL is not on 5432):

```bash
TEST_DATABASE_URL=postgresql://resume:resume@localhost:5432/resume_reviewer_test npm test
```

Each test rolls back its changes, and the suite drops and recreates every table in that database when it starts, so it always matches `db/schema.sql`. Never point it at `resume_reviewer`.

### npm scripts

All run from the repo root. They are defined in `package.json` and run Python through `scripts/py.mjs`.

| Command | Runs |
| --- | --- |
| `npm run setup` | Creates `backend/.venv` if missing and installs the Python requirements |
| `npm run backend` | `uvicorn app.main:app --reload` in `backend/` |
| `npm run frontend` | A static server for `frontend/` on port 5500 |
| `npm run lint` | `ruff check .` in `backend/` |
| `npm test` | `pytest` in `backend/` |
| `npm run check` | `lint`, then `test`, the same checks CI runs |

If `setup` picks the wrong Python, set `PYTHON` to the interpreter path first, e.g. `PYTHON=python3.12 npm run setup`.

<details>
<summary>Without npm</summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload    # backend
ruff check . && pytest           # lint and tests
python -m http.server 5500 --directory ../frontend   # frontend, in another terminal
```

</details>

## Workflow

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching, commits, and pull requests.

Short version: nobody, human or AI, commits to `main`. Every task gets its own branch off the latest `main` and lands through a reviewed pull request.

```bash
git fetch origin
git switch -c feature/your-task origin/main
```

## Working with AI agents

The team uses two coding agents. Both follow the same rules.

| Tool | Model | Reads |
| --- | --- | --- |
| Claude Code | Opus 5.5 | [CLAUDE.md](CLAUDE.md), which imports [AGENTS.md](AGENTS.md) |
| ChatGPT Codex | Sol | [AGENTS.md](AGENTS.md) |

[AGENTS.md](AGENTS.md) is the single rulebook. Change shared rules there, never in `CLAUDE.md`, so the two tools cannot drift apart. Changes to it go through a pull request like any other file.

What the agents are told to do:

- **Check the branch first.** If a session starts on `main`, the agent creates a feature branch before editing anything.
- **Stay on their own branch.** No commits or pushes to `main`, no merging, no force pushes, and no touching a teammate's branch or uncommitted work without asking.
- **Open their own PRs.** When a task is done and checks pass, the agent commits, pushes its feature branch, and opens a PR into `main` with the template filled in. A teammate reviews and merges. Agents never merge.
- **Keep diffs small.** One task per branch. Unrelated bugs get reported, not quietly fixed in the same PR.
- **Prove it works.** `npm run check` (ruff and pytest) passes, the changed flow is actually run, and the report says which checks ran and which could not.
- **Flag team decisions.** Schema changes, new dependencies, API shape changes, and scoring weights need a human OK.

Tips for teammates:

- Start each agent session by naming the task and its requirement IDs, e.g. "Build the ATS rule scorer, FR-9 and FR-10."
- Running two agents at once? Give each its own worktree so they don't overwrite each other:

  ```bash
  git worktree add ../rr-ats-scorer -b feature/ats-scorer origin/main
  ```

- Read your agent's PR before you ask a teammate to review it. You own every line in it, including the ones the agent wrote.
- When an agent hits a non-obvious pitfall, add one line to the Sharp edges section of `AGENTS.md` so the next session avoids it.

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
