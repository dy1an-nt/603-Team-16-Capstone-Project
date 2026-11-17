# AGENTS.md

Operating rules for every AI coding agent in this repository: Claude Code
(Opus 5.5) and ChatGPT Codex (Sol). `CLAUDE.md` imports this file, so the
rules here bind both tools. Edit rules here, not in `CLAUDE.md`, so the two
never drift apart.

This is a four-person team project. Several people run agents against the
same GitHub repo at the same time, so the branch rules in section 2 matter
more than anything else in this file.

## 1. What this project is

Resume Reviewer, the CSC 603 Team 16 capstone. A user uploads a resume, gets
a rule-based ATS score, compares it to a job description for a match score,
and reviews LLM rewrite suggestions that are checked against the original
resume so nothing is invented.

Sources of truth, in order:

1. The requirements and design report, `docs/design-report.md` (original
   link in `docs/README.md`). It defines every `FR-*` and `NFR-*` ID, the
   API endpoints, the data model, the prompts, and the scoring formulas.
   `docs/api-contract.md` turns its endpoints into request and response
   examples. Read only the sections your task touches.
2. The code itself: `backend/requirements.txt` for installed libraries,
   `db/schema.sql` for tables, `backend/app/schemas.py` for API and LLM
   shapes, neighboring modules for patterns.
3. `README.md` for setup and commands, `CONTRIBUTING.md` for team workflow.

Do not copy route lists, table lists, or folder trees into this file or
into new docs. Copies go stale. Point at the file that owns the fact.

## 2. Branches (non-negotiable)

`main` is shared and always runnable. Agents never change it directly.

Before the first edit of a session:

1. Run `git status` and `git branch --show-current`.
2. If you are on `main`, stop and create a branch from the latest `main`:

   ```bash
   git fetch origin
   git switch -c feature/<short-task-name> origin/main
   ```

   Prefixes match `CONTRIBUTING.md`: `feature/`, `fix/`, `docs/`, `chore/`.
   Use lowercase and hyphens, e.g. `feature/ats-scorer`, `fix/pdf-empty-text`.
3. If you are already on a feature branch, confirm it is the branch for this
   task. If it belongs to a different task or a teammate, ask before
   touching it.
4. If `git status` shows uncommitted changes you did not make, leave them
   alone. They are someone's work in progress. Ask before stashing,
   committing, or discarding them.

While working:

- One task, one branch, one pull request. Do not mix unrelated changes into
  a branch because it is already open.
- Never commit to `main`, push to `main`, or merge a pull request.
- Never delete a branch, local or remote, including after its pull request
  merges. The team keeps merged branches.
- Never force push, `git reset --hard`, or rebase a branch that has been
  pushed, unless the human asked for that exact command. Teammates may have
  pulled it.
- To pick up new work from `main`, merge it in:
  `git fetch origin && git merge origin/main`. Resolve conflicts by reading
  both sides. Never resolve a conflict by blindly taking "ours" or
  "theirs" on a file someone else owns.
- Running two agent sessions at once? Give each its own worktree so they
  cannot overwrite each other:
  `git worktree add ../rr-<task> -b feature/<task> origin/main`.

When the task is done and every check in section 6 passes, finish it
without waiting to be asked:

1. Commit to the feature branch.
2. Push the feature branch: `git push -u origin <branch>`.
3. Open a pull request into `main` with `gh pr create --base main`. Fill in
   `.github/pull_request_template.md`: what changed, requirement IDs, how
   to test, and the checklist. List any check that did not run, any
   schema SQL teammates must apply, and any assumptions you made.
4. Report the pull request link to the human.

Do not push or open a pull request while a check is failing or the work is
partial. If the human wants an early look, open it as a draft
(`gh pr create --draft`) and say what is unfinished. Never merge your own
pull request. A human teammate reviews and merges.

Commit messages follow `CONTRIBUTING.md`: short, present tense, one change,
requirement ID when it helps (`Add grounding check (FR-18)`). Do not add
`Co-Authored-By` trailers or other AI attribution lines to commits or pull
requests.

## 3. Before you edit

- A question asks for analysis, not a code change. Answer it and stop.
  Edit only when asked.
- Read the file you are about to edit, in this session. Never edit from
  memory or from what another file implies about it.
- Read its immediate neighbors too: router, the service it calls, the
  schema it returns. For frontend work, the page and `frontend/js/api.js`.
- Copy the closest existing pattern. New structure needs a stated reason.
- Never invent an API. Before calling a library function you have not read
  this session, confirm the package is in `backend/requirements.txt` and
  check its real signature. If you cannot verify it, say so.
- Verify model IDs, prices, and provider behavior against the provider's
  docs or a real call, never from training data. Model catalogs change.

## 4. Scope

- Smallest complete change that solves the task. No drive-by refactors,
  renames, or reformatting of lines you did not need to touch.
- Found a second bug? Report it. Do not fold it into this diff.
- Stay inside your task's area. Another teammate likely owns the file next
  door this week. If the task truly needs a change elsewhere, say so in the
  pull request description.
- Adding a dependency, changing the database schema, changing an API
  request or response shape, or reorganizing folders affects the whole
  team. Explain why and get the human's OK first.

## 5. Project rules

These come from the report's requirements. Breaking one is a bug, not a
style choice.

- **Scores are deterministic** (NFR-3). ATS and match scoring are plain
  Python with no LLM and no randomness. The same input gives the same score
  every run.
- **The LLM is optional** (NFR-4). Parsing and ATS scoring never call it,
  so they work when Groq fails or times out. A request that needs the LLM
  fails with `502` and saves nothing. The user can retry or fall back to an
  ATS-only analysis (`docs/api-contract.md`).
- **LLM output is untrusted.** Validate every response with the Pydantic
  schema, retry once, then return a clear error (NFR-5). Never execute LLM
  output. Wrap user text in tags and treat it as data (prompt injection).
- **The grounding check is code, not a prompt** (FR-18, NFR-6). The backend
  flags new skills, numbers, and proper nouns. Do not rely on the model to
  police itself.
- **Every query is parameterized** (NFR-12) and lives in the data layer,
  never built with string formatting in a router.
- **Every endpoint except register and login requires auth** (NFR-8), and
  every resume, analysis, and revision lookup checks it belongs to the
  current user (NFR-9). Return 404 for another user's record.
- **Secrets stay on the server** (NFR-10). Read keys through
  `app/config.py`. Never put a key in frontend code, a test, a log line, or
  a commit.
- **Resume text is personal data.** Do not log it. Do not commit real
  resumes. Test files go in `backend/tests/fixtures/` and are synthetic or
  anonymized.
- **Tunable numbers live in one place.** Match weights, ATS rule weights,
  and limits are constants the code reads. The UI shows those constants, it
  never retypes them.

## 6. Done means verified

Work is not done until each line is true. If a check failed or could not
run, say so plainly. "Should work" is not a status.

1. `npm run lint` (`ruff check .` in `backend/`) passes.
2. `npm test` (`pytest` in `backend/`) passes. New logic in `services/` has a test,
   including at least one bad-input case. LLM code is tested with a fake
   client. Tests never call Groq.
3. The changed flow was exercised, not just written: hit the endpoint with
   `curl` or `/docs`, or load the page and click through it. If you could
   not run it (no database, no API key), say exactly what was not run.
4. You re-read the full diff after your last edit, including new files.
   Plain `git diff` hides untracked files, so check `git status` too.
5. Schema change? `db/schema.sql` uses `IF NOT EXISTS`, so editing it does
   not change an existing database. Say so in your summary and in the pull
   request, with the SQL teammates must run.
6. Your report lists which checks ran, which passed, and which did not run.

## 7. When stuck

Two failed attempts at the same fix means stop. Re-read the exact error and
re-derive the cause before a third try. If it is still failing, write a
short handoff instead of looping:

- the exact error, verbatim
- the suspected cause
- the files involved
- what you tried and why each attempt failed
- the current state of the branch (working, partly working, or reverted)
- the next step you recommend

Before fixing a bug, check the sharp edges below. When you confirm a new
non-obvious pitfall, add one line here in the same pull request.

## 8. Sharp edges

- `app/config.py` reads `.env` from the repo root (`../.env`) and from
  `backend/`. Run the backend from `backend/` or settings fall back to
  defaults silently.
- `db/schema.sql` only creates missing tables. Edits to an existing table
  need an `ALTER TABLE` statement shared with the team (section 6, item 5).
  Those live in `db/migrations/` and are applied by hand. A 500 with
  `UndefinedColumn` in the backend log means one was never run locally.
- `frontend/js/api.js` hardcodes `API_BASE = "http://localhost:8000"`. The
  report's deploy plan changes it to a relative path. Do not add a second
  base URL anywhere.
- `sentence-transformers` is commented out in `requirements.txt` until
  Week 5. It is a large download. Load the model once at startup, never per
  request.
- DOCX page count and rendered layout come from LibreOffice (`soffice`).
  It is best effort: if it is missing or fails, the upload still succeeds
  and `page_count` is `None`. Each run needs its own `-env:UserInstallation`
  profile, or concurrent conversions fail silently.
- psycopg's `conn.transaction()` commits on exit when it is the first
  statement on a connection, which breaks the one-transaction-per-request
  rule in `db.get_db`. Inside a repository, use explicit `SAVEPOINT`
  statements instead (see `UserRepository.create`).
- `tests/test_repositories.py` skips unless `TEST_DATABASE_URL` is set, so a
  local green run without it proves nothing about the data layer. CI sets it.
- A `204` route that returns `None` still sends `content-type:
  application/json` with an empty body. Return `Response(status_code=204)`
  (see `routers/auth.py`). `api.js` skips parsing any 204 for the same reason.
- bcrypt 5 raises on passwords over 72 bytes instead of truncating. Hash and
  check through `app/security.py`, which truncates the same way both times.

## 9. Writing

- Plain, direct English in code comments, docs, commit messages, and pull
  requests. Lead with the result.
- No em dashes. Use a period or a comma.
- Comments explain a constraint the code cannot show. They do not narrate
  what changed or restate the next line.
- Match the surrounding file's naming, structure, and comment density.

## 10. What agents do not decide

These belong to the team: product scope beyond the report, API contract
changes, schema changes, new dependencies, scoring weights, anything that
costs money, deploys, and merging to `main`. If the report is unclear on
something small, pick the simplest option, do it, and write the assumption
in the pull request description.
