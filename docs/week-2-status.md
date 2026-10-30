# Week 2 status: accounts and auth

Milestone: Oct 26 to Nov 1, 2026, FR-1 to FR-3 ([design-report.md](design-report.md)
section 14). Endpoint shapes: [api-contract.md](api-contract.md). Last updated Oct 29.

## Checklist

- [x] FR-1 register: bcrypt hash (NFR-7), 409 duplicate email, 422 bad input
- [x] FR-2 login: HS256 JWT with `exp`, same 401 for wrong email or password
- [x] FR-2 logout: authenticated, 204, client drops token
- [x] FR-3 delete account: cascades to every table (NFR-14), old token then gets 401
- [x] NFR-8: every route except register, login, and health needs a bearer token
- [x] Minimal account form in `frontend/index.html` (register, log in, log out, delete)
- [ ] Teammate review of PR #6 (data layer and `job_descriptions` schema change)
- [ ] Teammate review of PR #7 (auth), then retarget it to `main` after PR #6 merges
- [ ] Frontend team restyles the account form (structure and IDs below)

## Pull requests

| PR | Branch | State |
| --- | --- | --- |
| [#6](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/6) | `feature/db-repositories` | Open, CI green, needs review. Auth builds on it. |
| [#7](https://github.com/dy1an-nt/603-Team-16-Capstone-Project/pull/7) | `feature/auth-accounts` | Open, base is `feature/db-repositories` (stacked on #6). Needs review. |

## Blockers

- The auth PR cannot merge before PR #6. It needs `UserRepository` and `get_db` from #6.
  Merge #6 first, then change the auth PR's base to `main`.
- PR #6 changes `job_descriptions`. Anyone with a local database runs the SQL in its
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

1. A teammate reviews and merges PR #6.
2. Retarget the auth PR to `main`, then a teammate reviews and merges it.
3. Week 3 (FR-4 to FR-8) starts from `main` after both merge.
