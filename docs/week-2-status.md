# Week 2 status: accounts and auth

Milestone: Oct 26 to Nov 1, 2026, FR-1 to FR-3 ([design-report.md](design-report.md)
section 14). Endpoint shapes: [api-contract.md](api-contract.md). Last updated Oct 29 (evening).

## Checklist

- [x] FR-1 register: bcrypt hash (NFR-7), 409 duplicate email, 422 bad input
- [x] FR-2 login: HS256 JWT with `exp`, same 401 for wrong email or password
- [x] FR-2 logout: authenticated, 204, client drops token
- [x] FR-3 delete account: cascades to every table (NFR-14), old token then gets 401
- [x] NFR-8: every route except register, login, and health needs a bearer token
- [x] Minimal account form in `frontend/index.html` (register, log in, log out, delete)
- [x] PR #6 (data layer and `job_descriptions` schema change) merged Oct 29
- [x] PR #7 (auth) retargeted to `main`
- [ ] Teammate review and merge of PR #7 (auth)
- [ ] Teammate review and merge of PR #8 (npm scripts, not a Week 2 requirement)
- [ ] Frontend team restyles the account form (structure and IDs below)

## Pull requests

| PR | Branch | State |
| --- | --- | --- |
| [#6](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/6) | `feature/db-repositories` | Merged Oct 29. |
| [#7](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/7) | `feature/auth-accounts` | Open against `main`. Needs a teammate review. |
| [#8](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/8) | `chore/npm-scripts` | Open against `main`. Needs a teammate review. Adds Node 18+ as a prerequisite. |

## Blockers

- None blocking. PR #7 waits only on a teammate review.
- PR #6 changed `job_descriptions`. Anyone with a local database runs the SQL in its
  description once.
- `pyjwt` is a new dependency. Run `pip install -r requirements.txt` after pulling.

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

1. A teammate reviews and merges PR #7 by Nov 1.
2. A teammate reviews PR #8. After it merges, `npm run setup` and `npm run check` replace the
   pip, ruff, and pytest commands.
3. Week 3 (FR-4 to FR-8) starts from `main` after PR #7 merges.
