@AGENTS.md

# Claude Code notes

Everything above comes from `AGENTS.md`, which Codex also reads. Put shared
rules there. This file holds only what is specific to Claude Code (Opus 5.5).

## Session start

Check the branch before anything else (`AGENTS.md` section 2). If the
session opened on `main`, create a feature branch before the first edit.

## Working style

- Act when the request is clear and the action is reversible. Pushing a
  feature branch and opening its pull request are part of finishing a task
  (`AGENTS.md` section 2). Ask first for destructive actions (deleting
  data, force pushes), deploys, merges, and real scope changes.
- Decide once. Do not re-open a decision the human or the report already
  made. When a real choice comes up, give one recommendation and the
  reason.
- Lead the final message with the outcome. Quote real command output for
  test and lint results.
- Spend tokens carefully. Batch independent tool calls, read the part of a
  file you need, and do not re-read a file just to confirm an edit landed.
- Do not spawn subagents unless the human asks. Each one starts cold.

## Review before the pull request

An implementing session does not sign off on its own work. Before pushing
and opening the pull request, run `/code-review` on the branch and fix or
answer each finding. A teammate's review on GitHub is still required to
merge.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues, managed with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
