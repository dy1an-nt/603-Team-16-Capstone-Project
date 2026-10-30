# API contract

The agreement between the backend and the frontend, so both can be built at
the same time. It covers every endpoint in report section 8
([design-report.md](design-report.md)). The Pydantic models in
`backend/app/schemas.py` are the source of truth for field names and types.
This page adds one example per endpoint and the rules that apply to all of
them. Example values are illustrative, and examples leave out the
`Authorization` header. With the backend running, `http://localhost:8000/docs`
shows the same models.

Change this contract only with the team's agreement (`AGENTS.md` section 10).
Update `schemas.py` and this page in the same pull request.

## Rules for every endpoint

### Auth

- Login returns a short-lived JWT (NFR-8). The frontend sends it on every
  other request as `Authorization: Bearer <access_token>`.
  `frontend/js/api.js` stores it in `sessionStorage` and adds the header.
- The token expires after `access_token_expire_minutes` from
  `backend/app/config.py`. There is no refresh token. When it expires, the
  user logs in again.
- Every endpoint except `POST /auth/register` and `POST /auth/login` requires
  the token. A missing, invalid, or expired token returns `401` with a
  `WWW-Authenticate: Bearer` header. `api.js` drops the stored token on any
  `401`.
- A token in `sessionStorage` can be read by any script on the page, so the
  frontend renders user and LLM text with `textContent`, never `innerHTML`.
- A resume, analysis, or revision that belongs to another user returns `404`,
  the same as one that does not exist (NFR-9). Never `403`, which would
  confirm the record exists.

### Errors

Every error uses FastAPI's shape:

```json
{ "detail": "Resume not found" }
```

`detail` is a short message safe to show the user. One exception: request
validation failures (`422` from FastAPI itself, for example a missing field
or a password under 8 characters) return `detail` as a list:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 8 characters",
      "input": "short",
      "ctx": { "min_length": 8 }
    }
  ]
}
```

The frontend should show `detail` when it is a string and the first item's
`msg` when it is a list.

| Status | When |
| --- | --- |
| 400 | Request is well formed but cannot be processed (for example, a parsed resume with no text) |
| 401 | Missing, invalid, or expired token, or wrong email or password at login |
| 404 | Record does not exist or belongs to another user |
| 409 | Email already registered |
| 413 | Upload larger than 5 MB |
| 415 | Upload is not a PDF or DOCX |
| 422 | Request body or query failed validation |
| 502 | The LLM failed or returned invalid output after one retry (NFR-5). Returned by `POST /analyses` with a job description and by `POST /analyses/{id}/revisions`. Nothing is saved. |

### Conventions

- JSON bodies use `Content-Type: application/json`, except the resume upload
  (`multipart/form-data`) and the export download.
- IDs are integers. Timestamps are ISO 8601 with a UTC offset.
- Scores are integers from 0 to 100.

## Endpoints

### POST /auth/register (FR-1)

No auth. Creates an account. Does not log the user in.

```http
POST /auth/register
Content-Type: application/json

{ "email": "sam@example.com", "password": "correct-horse" }
```

`201 Created`

```json
{ "id": 7, "email": "sam@example.com", "created_at": "2026-10-14T18:02:11Z" }
```

Errors: `409` email taken, `422` invalid email or password under 8 characters.

### POST /auth/login (FR-2)

No auth. Returns the JWT.

```http
POST /auth/login
Content-Type: application/json

{ "email": "sam@example.com", "password": "correct-horse" }
```

`200 OK`

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer", "expires_in": 3600 }
```

`expires_in` is in seconds.

Errors: `401` with `{"detail": "Invalid email or password"}`. The message is
the same whether the email or the password was wrong.

### POST /auth/logout (FR-2)

JWTs are stateless, so the server keeps no session to end. The endpoint
exists so the frontend has one logout call. The frontend discards its token
whatever the response.

```http
POST /auth/logout
```

`204 No Content`, no body.

### DELETE /account (FR-3)

Deletes the user and, by cascade, every resume, job description, analysis,
and revision they own (NFR-14). The frontend then discards its token.

```http
DELETE /account
```

`204 No Content`, no body.

### POST /resumes (FR-4 to FR-8)

Uploads and parses a PDF or DOCX, up to 5 MB. The form field is `file`.

```http
POST /resumes
Content-Type: multipart/form-data; boundary=...

file=@resume.pdf
```

`201 Created`

```json
{
  "id": 12,
  "filename": "resume.pdf",
  "created_at": "2026-10-14T18:05:40Z",
  "sections": {
    "contact": "Sam Lee\nsam@example.com",
    "summary": "Backend developer with two years of Python experience.",
    "experience": "Software Intern, Acme\n- Built REST APIs in Python and PostgreSQL",
    "education": "B.S. Computer Science",
    "skills": "Python, SQL, JavaScript"
  }
}
```

`sections` keys come from `backend/app/services/parser.py`: `contact`,
`summary`, `education`, `experience`, `projects`, `skills`. A key is present
only when the resume has that heading. `contact` holds everything before the
first heading.

Errors: `413` over 5 MB, `415` not a PDF or DOCX, `400` image-only PDF or no
text extracted (FR-8).

### GET /resumes (FR-20)

Lists the current user's resumes, newest first. No section text.

```http
GET /resumes
```

`200 OK`

```json
[
  { "id": 12, "filename": "resume.pdf", "created_at": "2026-10-14T18:05:40Z" },
  { "id": 9, "filename": "resume-old.docx", "created_at": "2026-10-01T15:12:03Z" }
]
```

An empty list when the user has none.

### GET /resumes/{id} (FR-7, FR-20)

```http
GET /resumes/12
```

`200 OK`, same shape as the `POST /resumes` response.

Errors: `404`.

### DELETE /resumes/{id} (FR-20)

Deletes the resume and, by cascade, its job descriptions, analyses, and revisions.

```http
DELETE /resumes/12
```

`204 No Content`, no body.

Errors: `404`.

### POST /analyses (FR-9 to FR-13)

Scores a saved resume. Send `job_description` (pasted text, FR-11) to also get
a match score. Leave it out for an ATS-only analysis.

```http
POST /analyses
Content-Type: application/json

{
  "resume_id": 12,
  "job_description": "Junior Backend Engineer. Required: Python, PostgreSQL, Docker. Preferred: AWS."
}
```

`201 Created`

```json
{
  "id": 31,
  "resume_id": 12,
  "job_description_id": 18,
  "ats_score": 85,
  "issues": [
    {
      "rule": "missing_projects",
      "message": "No 'Projects' section found.",
      "fix": "Add a section with the standard heading 'Projects'.",
      "penalty": 15
    }
  ],
  "job_requirements": {
    "job_title": "Junior Backend Engineer",
    "required_skills": ["Python", "PostgreSQL", "Docker"],
    "preferred_skills": ["AWS"],
    "responsibilities": []
  },
  "match_score": 33,
  "keywords": {
    "matched": ["Python", "PostgreSQL"],
    "missing": ["Docker", "AWS"]
  },
  "created_at": "2026-10-14T18:07:22Z"
}
```

`keywords` covers required and preferred skills together.

An ATS-only analysis has `job_description_id`, `job_requirements`,
`match_score`, and `keywords` all `null`. It never calls the LLM.

If job description extraction fails after one retry, the request fails with
`502` and nothing is saved, not even the ATS score. The frontend offers two
ways on (NFR-4): retry, or run an ATS-only analysis by sending the same
request without `job_description`.

Errors: `502` LLM extraction failed, `404` resume not found, `422` missing
`resume_id` or a blank `job_description`.

### GET /analyses/{id} (FR-20)

```http
GET /analyses/31
```

`200 OK`, same shape as the `POST /analyses` response.

Errors: `404`.

### POST /analyses/{id}/revisions (FR-14, FR-15, FR-18)

Asks the LLM for rewrite suggestions, then runs the grounding check in code.
No request body.

```http
POST /analyses/31/revisions
```

`201 Created`

```json
{
  "id": 44,
  "analysis_id": 31,
  "suggestions": [
    {
      "section": "experience",
      "original": "- Built REST APIs in Python and PostgreSQL",
      "revised": "- Built REST APIs in Python backed by PostgreSQL for internal tools",
      "reason": "Says what the APIs were for and keeps the stack the job asks for.",
      "keywords_added": [],
      "flagged": false,
      "flag_reasons": [],
      "accepted": null
    },
    {
      "section": "experience",
      "original": "- Built REST APIs in Python and PostgreSQL",
      "revised": "- Built REST APIs in Python and PostgreSQL, deployed with Docker",
      "reason": "Adds Docker, a required skill.",
      "keywords_added": ["Docker"],
      "flagged": true,
      "flag_reasons": ["new skill: Docker"],
      "accepted": null
    }
  ],
  "revised_text": null,
  "original_match_score": 33,
  "new_match_score": null,
  "created_at": "2026-10-14T18:09:51Z"
}
```

- `flagged` and `flag_reasons` come from `services/grounding.py`, never from
  the LLM (FR-18). The frontend must show flagged suggestions with their
  reasons.
- `accepted` is `null` until the user decides.
- `original_match_score` is the analysis's `match_score`, so the before and
  after scores (FR-17) sit in one response.
- An analysis without a job description can still get suggestions. Both match
  scores are then `null`.

Errors: `404` analysis not found, `502` the LLM failed or returned invalid
output after one retry (NFR-5). Nothing is saved on `502`.

### PATCH /revisions/{id} (FR-16, FR-17)

Records accept or reject decisions, rebuilds `revised_text` from the accepted
suggestions, and re-scores it. `index` is the suggestion's position in the
`suggestions` list, starting at 0. Suggestions not listed keep their current
`accepted` value.

```http
PATCH /revisions/44
Content-Type: application/json

{
  "decisions": [
    { "index": 0, "accepted": true },
    { "index": 1, "accepted": false }
  ]
}
```

`200 OK`, the full revision

```json
{
  "id": 44,
  "analysis_id": 31,
  "suggestions": [
    { "section": "experience", "original": "...", "revised": "...", "reason": "...", "keywords_added": [], "flagged": false, "flag_reasons": [], "accepted": true },
    { "section": "experience", "original": "...", "revised": "...", "reason": "...", "keywords_added": ["Docker"], "flagged": true, "flag_reasons": ["new skill: Docker"], "accepted": false }
  ],
  "revised_text": "Sam Lee\nsam@example.com\n\nExperience\nSoftware Intern, Acme\n- Built REST APIs in Python backed by PostgreSQL for internal tools\n...",
  "original_match_score": 33,
  "new_match_score": 33,
  "created_at": "2026-10-14T18:09:51Z"
}
```

Errors: `404` revision not found, `400` an `index` outside the suggestions
list, `422` empty `decisions` or the same `index` listed twice.

### GET /revisions/{id}/export (FR-19)

Downloads the revised resume. `fmt` is `txt` (default) or `docx`. Uses
`revised_text`, or the original resume text if no decision was made yet.

```http
GET /revisions/44/export?fmt=docx
```

`200 OK`, a file download, not JSON

```http
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="resume-revised.docx"
```

For `txt`, `Content-Type: text/plain; charset=utf-8` and
`filename="resume-revised.txt"`.

Errors: `404`, `422` any other `fmt`.

## Assumptions

Picked where the report left a choice open. Raise any of these with the team
before building on a different reading.

- Auth uses a JWT in the `Authorization` header, not a cookie (NFR-8 allows
  either). The report deploys the frontend and backend as separate Cloud Run
  services, and a header avoids cross-site cookie rules. Signing tokens needs
  a JWT library that is not in `requirements.txt` yet. The backend owner adds
  it with the auth work.
- Register does not log the user in. The frontend calls login next.
- Job descriptions are pasted text only. FR-11 also mentions upload. That
  can be added later as a separate field without breaking this shape.
- `POST /analyses` always stores the pasted text as a new `job_descriptions`
  row tied to that resume. There is no endpoint to list or reuse saved job
  descriptions.
- There is no `GET /analyses` list endpoint, since report section 8 does not
  have one. History (FR-20) lists resumes. Listing past analyses per resume
  needs a new endpoint and a team decision.
- Re-scoring (FR-17) recomputes only the match score, because `revisions`
  stores only `new_match_score`. A before and after ATS score would need a
  schema change.
