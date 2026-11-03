# ShopOS — Codex Working Rules

## Mission
Build a fast, employee-friendly Android app for recording and finding purchase bills. The app must fit the shop's current workflow and must not slow the counter.

## Product boundaries
- V1: employee login, bill ingest, vendor/item quick-create, proof photo, bill search, owner-only employee/permission management.
- A bill supports multiple line items.
- No sales, inventory, accounting, OCR, analytics, or offline writes in V1 unless the product owner changes the PRD.
- Online-first. Local drafts and cached catalogs are allowed; PostgreSQL is authoritative.

## Stack
- Android: Kotlin, Jetpack Compose, Material 3, Room for drafts/cache, CameraX, Retrofit, Coroutines/StateFlow.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Alembic.
- Photos: private S3-compatible object storage using short-lived signed URLs.
- Tests: pytest, JUnit, Compose UI tests. Add checks only for the quest being implemented.

## Readable, changeable code
- Prefer small named functions and plain data models.
- Put bill form fields in `android/app/src/main/java/com/shopos/bills/form/BillFormFields.kt`.
- Each field declaration must state its label, input type, required status, and visibility. Do not scatter field labels across screens.
- Keep business rules in domain/service code, not Compose screens.
- Add comments to explain why a rule exists or where a product change belongs. Do not narrate obvious Kotlin/Python syntax.
- When adding a field, trace it through UI state, request/response models, backend validation, database migration, and query/detail screens as applicable.
- Backend validation is authoritative. UI required markers improve usability but never replace server validation.
- Money uses decimal types / integer paise; never binary floating point.

## Quest protocol and recovery
1. Read `PRD.md`, `QUESTS.md`, `progress.json`, and the relevant docs.
2. Inspect `git status`, recent commits, and the current implementation before editing.
3. Work on the earliest dependency-ready incomplete quest. Keep the change limited to that quest.
4. Run the quest's stated verification commands. Never claim a check passed unless it ran successfully.
5. Update `progress.json` with evidence and the next action.
6. Commit the quest's implementation, docs, and progress together after verification.
7. On interruption, preserve useful uncommitted work. Reconcile Git and `progress.json`; verify the unfinished quest before continuing.
8. If blocked, write the exact blocker and a concrete next step to `progress.json` and `docs/WORKLOG.md`.

## Safety
- Never commit credentials, `.env`, real customer/business data, or production photos.
- Never disable authentication or permission checks to make a feature work.
- Never delete production data, force-push, or rewrite shared history.
- Stage named files; do not blindly run `git add .`.
- Do not add libraries or infrastructure without a clear V1 need.

## Done means
A quest is done only when its acceptance criteria and checks are recorded. At completion, create `docs/FINAL_REPORT.md` with implemented scope, checks run, setup/deployment steps, remaining gaps, and APK location if one was built.
