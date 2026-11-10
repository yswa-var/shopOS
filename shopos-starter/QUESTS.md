# ShopOS — Build Quests

Complete one quest at a time. Each quest ends in a verified Git checkpoint. A quest can be split into smaller commits if needed, but do not mark it complete until all acceptance criteria pass.

| ID | Quest | Depends on | Acceptance evidence |
|---|---|---|---|
| Q00 | Repository, local backend/database setup, health endpoint, Android project shell, CI/check scripts | — | Clean setup documented; backend health responds; Android debug build works |
| Q01 | Employee authentication, owner bootstrap, RBAC, audit foundation | Q00 | Login/logout; unauthorized operations rejected in API tests |
| Q02 | Vendor/item catalog search, aliases, inline create | Q01 | Search and create endpoints; duplicate handling; Android selector flow |
| Q03 | Bill domain models, decimal-safe calculation and validation | Q02 | Unit tests cover quantity/rate/amount edits, rounding, optional tax/charges |
| Q04 | Private proof-photo upload and attachment metadata | Q01 | Upload/download authorization and failure/retry behavior documented and verified |
| Q05 | Android bill ingest, local draft recovery, idempotent save | Q03, Q04 | Multi-item bill with required photo saves exactly once; draft resumes |
| Q06 | Bill query, filters, detail, proof viewing | Q05 | Vendor/item/date/amount/employee search and permission behavior verified |
| Q07 | Owner employee and permission management | Q01 | Owner can create/deactivate/manage; employee access is denied |
| Q08 | Integration hardening and release handoff | Q02–Q07 | Full checks pass; setup and limitations recorded in `docs/FINAL_REPORT.md` |

## Quest template
For each quest, record in `docs/WORKLOG.md`:
- Scope and files changed
- Acceptance criteria completed
- Exact verification commands and outcomes
- Commit hash
- Any blocker or follow-up

## Dependency notes
Q04 can proceed as soon as Q01 is complete, even if Q02/Q03 are still underway. Keep its API contract documented so Q05 can integrate cleanly.
