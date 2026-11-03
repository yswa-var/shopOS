# Codex kickoff and recovery prompts

## First run

Paste this once in Codex with this folder open:

```text
Build ShopOS from this repository. First read AGENTS.md, PRD.md, QUESTS.md, progress.json, README.md, and docs/ARCHITECTURE.md. Inspect Git and the current files. Start with the earliest dependency-ready quest, currently Q00. Implement only that quest, run its stated verification, document exact results in docs/WORKLOG.md, update progress.json, and commit the verified checkpoint using a descriptive message. Then continue in quest order while checks pass. Do not claim unrun checks passed. If blocked, record the exact blocker and next action, then stop that quest without damaging useful work. Do not ask me to approve ordinary implementation details; make the simplest choice consistent with the PRD and document material tradeoffs.
```

## Resume after interruption

```text
Resume ShopOS. Read AGENTS.md, PRD.md, QUESTS.md, progress.json, and the latest docs/WORKLOG.md. Inspect Git status and recent commits; do not reset or discard uncommitted work. Reconcile progress.json with committed code and actual verification evidence. Re-run checks for any interrupted quest, then continue from the earliest dependency-ready incomplete quest. Commit only verified checkpoints and update the durable progress files.
```

## Change a requirement

```text
Change this ShopOS requirement: <describe change>. First identify every affected layer: PRD, Android field registry and UI state, API models and validation, database migration, query/detail behavior, and tests. Update the docs before implementation, then implement the smallest dependency-safe change. Keep backward compatibility or add a migration where stored data is affected. Verify the change and record it in docs/WORKLOG.md and progress.json.
```

## Git checkpoint pattern

```bash
git status --short
git add AGENTS.md PRD.md QUESTS.md progress.json README.md CODEX_START.md docs android backend
git commit -m "chore: start ShopOS Q00"
```

After Q00, Codex should stage only the files belonging to the verified quest and commit with a scope-specific message, for example `feat(bills): add decimal calculation rules`.
