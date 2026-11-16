# Week 3 status: resume upload and section display

Milestone: Nov 2 to 8, 2026, FR-4 to FR-8 ([design-report.md](design-report.md)).
Endpoint shapes: [api-contract.md](api-contract.md).
Last updated Nov 4. Frontend implementation is prepared; local verification and PR review are pending.

## Checklist

- [x] Restyle the Account form while preserving all existing element IDs
- [x] FR-4 frontend: upload PDF or DOCX resumes using `api.uploadResume`
- [x] FR-7: display contact, summary, education, experience, projects, and skills
- [x] FR-7: identify sections with no detected text
- [x] FR-8 frontend: show clear messages for 413, 415, and 400 responses
- [x] Render filenames and parsed text using `textContent` only
- [x] Show upload progress and prevent duplicate submissions
- [x] Handle expired sessions and clear parsed content on logout or account deletion
- [x] Add responsive styling for desktop and mobile widths
- [x] Lint and mocked frontend behavior checks pass
- [ ] Verify the layout in a browser at desktop and mobile widths
- [ ] Test PDF and DOCX uploads against the running backend and database
- [ ] Push `feature/upload-page` and open a pull request
- [ ] Teammate review and merge

## Pull requests

| PR | Branch | State |
| --- | --- | --- |
| Not opened | `feature/upload-page` | Preparing changes and local verification. |

## Review note

Checks on the prepared project snapshot passed: ruff, JavaScript syntax,
and mocked frontend behavior checks. Pytest reported 53 passed and 39
skipped. The skipped tests require PostgreSQL.

Mocked frontend checks covered successful upload, missing sections,
text-only rendering, 413/415/400/401 errors, duplicate submissions, and
logout during an upload.

Browser layout and live database-backed uploads still need verification.
No pull request has been opened or reviewed.

## Blockers

- Local backend and database setup must be completed before testing live uploads.
- Run `npm run setup` and configure `.env` according to `README.md`.
- A real browser check is still required because browser installation failed
  in the preparation environment.
- Live upload testing returns "Upload failed. Check that the backend is
  running and try again." Cause is undiagnosed. Upload and parsed-section
  display still need successful end-to-end verification.

## Frontend handoff

- Account markup stays in `section#account`. All IDs documented in
  `week-2-status.md` are preserved.
- Upload markup uses `form#upload-form`, `#resume-file`, and `#upload-btn`.
  Messages appear in `p#upload-status`.
- Parsed output appears in `section#parsed-resume`, with the filename in
  `#resume-filename` and section content in `#parsed-sections`.
- Behavior lives in `js/app.js`. Upload calls the existing
  `api.uploadResume(file)` helper.
- `js/api.js` preserves HTTP status codes as `error.status` so the page
  can show the appropriate upload error.
- The backend remains responsible for file validation and the configured
  size limit. No backend, database schema, or dependency changes are included.
- Job description and Analyze controls remain disabled placeholders for
  later milestones. Upload now has its own action.

## Next action (through Nov 8)

