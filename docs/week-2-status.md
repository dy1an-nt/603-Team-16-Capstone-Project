# Week 2 status: accounts and auth

Milestone: Oct 26 to Nov 1, 2026, FR-1 to FR-3 ([design-report.md](design-report.md)
section 14). Endpoint shapes: [api-contract.md](api-contract.md). Last updated Oct 29 (night). Week 2 is complete.

## Checklist

- [x] FR-1 register: bcrypt hash (NFR-7), 409 duplicate email, 422 bad input
- [x] FR-2 login: HS256 JWT with `exp`, same 401 for wrong email or password
- [x] FR-2 logout: authenticated, 204, client drops token
- [x] FR-3 delete account: cascades to every table (NFR-14), old token then gets 401
- [x] NFR-8: every route except register, login, and health needs a bearer token
- [x] Minimal account form in `frontend/index.html` (register, log in, log out, delete)
- [x] PR #6 (data layer and `job_descriptions` schema change) merged Oct 29
- [x] PR #7 (auth) merged Oct 29
- [x] PR #8 (npm scripts, not a Week 2 requirement) merged Oct 29
- [ ] Frontend team restyles the account form (structure and IDs below)

## Pull requests

| PR | Branch | State |
| --- | --- | --- |
| [#6](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/6) | `feature/db-repositories` | Merged Oct 29. |
| [#7](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/7) | `feature/auth-accounts` | Merged Oct 29. |
| [#8](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/8) | `chore/npm-scripts` | Merged Oct 29. Adds Node 18+ as a prerequisite. |

## Review note

On Dylan's instruction, PR #7 and PR #8 were merged after review by the Claude Code
session that wrote them, plus a combined test of `main` with both. No teammate reviewed
them first, which is an exception to `CONTRIBUTING.md`.

## Blockers

- None.
- PR #6 changed `job_descriptions`. Anyone with a local database runs the SQL in its
  description once.
- After pulling `main`: run `npm run setup` (installs the new `pyjwt` dependency) and set a
  `SECRET_KEY` of at least 32 bytes in `.env`, or login returns 500.

## Frontend handoff

- Markup: `section#account` in `index.html`. `form#auth-form` holds `#auth-email`,
  `#auth-password`, `#login-btn`, and `#register-btn`. `div#account-actions` holds
  `#logout-btn` and `#delete-account-btn`. Messages go to `p#account-status`.
- Behavior lives in `js/app.js` (`renderAccount`). Keep the IDs, or update both files
  together. Restyling is the frontend team's call. The form uses only existing classes.
- `api.js` added `deleteAccount()` and `isLoggedIn()`. The token stays in
  `sessionStorage` and is dropped on logout, delete, and any 401.
- Upload and results are still placeholders. Upload now returns 401 when logged out and
  "upload not implemented" (501) when logged in, until Week 3.

## Next action (through Nov 1)

1. Week 3 (FR-4 to FR-8, upload and parsing) starts from `main`. Owners confirm on Discord.
2. A teammate reads PR #7 and PR #8 after the fact and raises anything they would have
   blocked.
