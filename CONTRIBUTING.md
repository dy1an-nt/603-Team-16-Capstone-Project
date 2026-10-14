# Contributing

## Branches

- `main` is always runnable. No direct pushes; changes go through pull requests.
- Create a branch per task:

| Prefix | Use |
| --- | --- |
| `feature/` | New functionality, e.g. `feature/ats-scorer` |
| `fix/` | Bug fixes, e.g. `fix/pdf-empty-text` |
| `docs/` | Documentation only |
| `chore/` | Setup, dependencies, config |

```bash
git checkout main
git pull
git checkout -b feature/your-task
```

## Commits

Short, present tense, one change per commit:

```
Add PDF section parser
Fix match score when job description has no skills
```

Reference the requirement when it helps: `Add grounding check (FR-18)`.

## Pull requests

1. Push your branch and open a PR into `main`.
2. Fill in the PR template.
3. CI (lint + tests) must pass.
4. At least one teammate reviews and approves.
5. Squash and merge, then delete the branch.

Keep PRs small. One feature or fix per PR is easier to review than a week of work at once.

## Before opening a PR

```bash
cd backend
ruff check .
pytest
```

## Rules

- Never commit `.env`, API keys, or real resumes with personal info.
- Test resumes go in `backend/tests/fixtures/` and must be synthetic or anonymized.
- New backend logic in `services/` needs at least one unit test.
- Post progress or blockers in Discord at least once a week.
