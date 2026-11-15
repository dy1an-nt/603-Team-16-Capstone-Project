# Week 3 status: resume upload and section display

Milestone: Nov 2 to 8, 2026, FR-4 to FR-8 ([design-report.md](design-report.md)).
Endpoint shapes: [api-contract.md](api-contract.md).

Last updated Nov 15. Week 3 frontend implementation and live testing are
complete. Upload page cleanup and the resume ID handoff are in PR #15.

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
- [x] Verify the layout in a browser at desktop and mobile widths
- [x] Test PDF and DOCX uploads against the running backend and database
- [x] Push `feature/upload-page` and open a pull request
- [x] Teammate review and merge

## Pull requests

| PR | Branch | State |
| --- | --- | --- |
| [#11](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/11) | `feature/upload-page` | Merged. Lead verified PDF/DOCX uploads and upload error messages on PostgreSQL. |

## Review note

Checks on the prepared project snapshot passed: ruff, JavaScript syntax,
and mocked frontend behavior checks. Pytest reported 53 passed and 39
skipped. The skipped tests require PostgreSQL.

Mocked frontend checks covered successful upload, missing sections,
text-only rendering, 413/415/400/401 errors, duplicate submissions, and
logout during an upload.

Live PDF/DOCX uploads, parsed sections, 413/415/400 messages, logout/login,
and desktop/mobile layouts passed verification on Nov 9. The lead also
confirmed live upload testing on PostgreSQL. PR #11 was merged.

## Blockers

- None for Week 3 upload functionality. The lead confirmed that the earlier
  generic upload failure came from a local backend crash.

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
- `window.currentResumeId` holds the ID returned after a successful upload.
  It is `null` initially and clears on file selection, a new upload attempt,
  logout, or account deletion.
