
# ShopOS — Telegram Bill Ingestion to ERPNext

**Version:** 1.0  
**Status:** Proposed for implementation  
**Development:** Codex  
**Architecture:** aiogram + SQLite + S3 + ERPNext REST API  
**Principle:** Extend the existing implementation. Do not rewrite functioning components.

---

## 1. Product overview

ShopOS is an internal Telegram-based bill-ingestion system for a grocery business.

Employees communicate in Hindi, Hinglish or English to enter purchase bills, upload proof images, correct extracted fields and confirm financial records.

The existing implementation already supports:

- Telegram access control.
- Incremental structured extraction through OpenRouter.
- Vendor, account and item resolution.
- Persistent SQLite drafts.
- Image staging and local proof storage.
- Bill preview, editing and confirmation.
- Atomic local bill creation.
- Duplicate confirmation protection.

The next version will integrate ERPNext as the authoritative destination for purchase invoices and business master data, and S3-compatible object storage for proof images.

### Primary goal

An employee can enter a bill over multiple Telegram messages, stop midway, resume later, correct errors and confirm the completed bill.

The system then creates **exactly one corresponding ERPNext Purchase Invoice draft**, without silently losing data or duplicating invoices.

Financial ledger submission remains a separate, authorized action.

### Non-goals

- Rebuilding ERPNext accounting.
- Developing a separate REST API.
- Deploying Temporal, Restate or DBOS.
- Implementing a distributed event bus.
- Replacing aiogram.
- Rewriting the existing extraction pipeline.
- Replacing or modifying `pricebot/`.
- Building a web dashboard.
- Automatically submitting, paying or approving ERPNext invoices.
- Implementing complete PO/GRN matching in this release.

---

## 2. System architecture

```text
Telegram
    |
    v
Existing allowlist middleware
    |
    v
Existing aiogram handlers
    |
    v
Existing BillEntryService
    |
    +----> OpenRouter structured extraction
    |
    +----> EntityResolver
    |         |
    |         +----> ERPNext master-data lookup
    |         +----> SQLite cache (optional)
    |
    v
SQLite persistent draft
    |
    +----> S3-compatible proof storage
    |
    v
Existing confirmation service
    |
    +----> Validate
    +----> Preview
    +----> Edit / Confirm
    |
    v
ERPNext integration service
    |
    +----> Revalidate references
    +----> Reconcile prior attempts
    +----> Create Purchase Invoice draft
    +----> Verify invoice ID
    |
    v
SQLite posting record
    |
    v
Telegram success notification
```

### Architectural boundaries

**Telegram:** User interface, interaction and notifications.

**OpenRouter:** Natural-language interpretation only.

**SQLite:** Drafts, processing state, temporary metadata, posting attempts and audit mappings.

**S3:** Original proof images.

**ERPNext:** Authoritative suppliers, companies, items, purchase invoices, accounting and inventory.

**Python application:** Business coordination, validation and recovery.

No separate public HTTP server is required. Telegram uses long polling, while ERPNext and S3 are accessed through outbound requests.

---

## 3. Existing code preservation

The following existing components must remain the foundation of the implementation:

| Existing component | Required action |
|---|---|
| `main.py` | Extend dependency wiring and startup |
| `config.py` | Extend Pydantic settings |
| `bot/middleware.py` | Preserve allowlist behavior |
| `bot/handlers.py` | Extend callbacks and status reporting |
| `services/draft_service.py` | Extend states and metadata |
| `services/bill_entry_service.py` | Preserve incremental merging |
| `services/entity_resolver.py` | Add ERPNext-backed resolution |
| `services/confirmation_service.py` | Change final persistence destination |
| `services/proof_storage.py` | Add S3 backend |
| `llm/client.py` | Preserve integration |
| `llm/extractor.py` | Preserve extraction behavior |
| `llm/schemas.py` | Extend only when required |
| `db/migrations.py` | Add forward-only migrations |

Keep the existing local SQLite bill implementation available during migration. Do not immediately delete `bills`, `bill_items`, `vendors`, `accounts` or `items`.

Before implementation, Codex must inspect the actual repository and identify callers, database dependencies and current test coverage.

The architecture provided here is the specification; existing code remains the authority on current function signatures.

---

## 4. Functional requirements

### FR-01: Start or resume a bill

Triggers:

- `/upload_bill`
- A valid text message
- A valid proof image

Behavior:

1. Identify the authorized Telegram user.
2. Find their active draft.
3. Resume it if available.
4. Otherwise create a new draft with a UUID.
5. Persist state before acknowledging the new draft.

One active draft per user remains the default.

`/status` must show the bill ID, state, missing fields, image presence and latest posting status.

`/cancel` must cancel only drafts that have not been posted to ERPNext. It must never delete an existing ERPNext invoice.

### FR-02: Structured text extraction

Reuse the existing OpenRouter extraction logic.

Input:

- Current draft JSON.
- Latest Telegram text message.
- Existing strict extraction schema.

Output:

- Field changes.
- Item add/update/remove instructions.
- Ambiguity metadata when supported.

Requirements:

- Preserve existing fields unless explicitly modified.
- Treat missing values differently from explicit zero or null values.
- Prevent LLM-generated database IDs.
- Do not allow the model to execute database actions.
- Never infer missing financial values without an explicit business rule.
- Keep the draft unchanged if extraction fails.
- Retry only transient extraction failures with bounded attempts.

For ambiguous updates, request clarification before mutating the affected field.

### FR-03: Missing-field handling

Preserve existing required fields:

- Vendor.
- Account.
- Firm name for a new account.
- At least one item.
- Valid quantity and unit price.
- Due date.
- Proof image.

Add ERPNext posting requirements:

- Resolved ERPNext Supplier.
- Resolved ERPNext Company.
- Resolved ERPNext Item codes.
- Valid item UOM.
- Required accounting, tax and warehouse information where applicable.
- Supplier invoice reference and date according to configured business policy.
- Any mandatory fields required by the target ERPNext instance.

**Important:** The existing ShopOS account is not automatically an ERPNext Company or accounting ledger. Explicitly define mappings for legacy accounts, firms and ERPNext Companies before posting.

The system should ask concise questions, preferably one unresolved decision at a time.

Example:

```text
Missing: Supplier

Found two matches:
1. Gupta Traders
2. Gupta Trading Co.

Select the correct supplier.
```

### FR-04: Corrections and state updates

An employee may send:

```text
Change haldi to 6 kg
```

The system must:

1. Load the current draft.
2. Interpret the change.
3. Resolve the affected item.
4. Update the appropriate fields.
5. Recalculate dependent amounts.
6. Increment draft revision.
7. Persist the updated draft.
8. Revalidate the draft.
9. Invalidate any older confirmation button.

Required behavior:

- Adding an item does not replace unrelated items.
- Editing one line does not overwrite other lines.
- Removing an item updates totals.
- Changing the vendor invalidates the old vendor resolution.
- Changing company/account mappings triggers necessary revalidation.
- Any financial correction invalidates an earlier approval preview.

All monetary calculations must use integer paise or decimal arithmetic, never binary floating-point arithmetic.

### FR-05: Entity resolution

Extend `EntityResolver` to use ERPNext master data.

Target entities:

- Supplier.
- Company.
- Item.
- UOM.

Optional later entities:

- Warehouse.
- Purchase Order.
- Purchase Receipt.
- Cost Center.

Matching order:

1. Existing verified ERPNext ID mapping.
2. Normalized exact match.
3. Configured aliases.
4. High-confidence unique match.
5. User clarification.

Do not automatically select among multiple similar records.

Unknown entities must not automatically create accounting or inventory master records.

Instead, mark the draft as needing entity setup or authorized review.

For the initial release, use existing ERPNext masters and manually configured mappings.

The local SQLite registry can remain as a cache, but ERPNext is authoritative after migration.

### FR-06: Image ingestion and S3 storage

Replace permanent local proof storage with an S3-compatible storage backend.

Required behavior:

1. Receive Telegram photo or image document.
2. Check allowed file type and size.
3. Download and stage the image.
4. Upload the original to S3-compatible storage.
5. Verify upload success.
6. Persist its object key, checksum and metadata in SQLite.
7. Delete the temporary local file when safe.

Suggested object key:

```text
shopos/parchi/YYYY/MM/DD/<draft_uuid>/<image_uuid>.jpg
```

Never store expiring presigned URLs as permanent references.

Store object keys and generate temporary access URLs when needed.

The bucket must be private.

Required image metadata:

- `draft_id`
- `object_key`
- `content_type`
- `size_bytes`
- `sha256`
- `uploaded_at`
- `storage_status`

Use the existing local proof-storage backend for development and backwards compatibility.

**Image replacement:** Upload and persist the new proof reference before removing the old reference. Retain the old object until the new update is verified.

**Orphan cleanup:** Use a scheduled cleanup process for abandoned uploads, with a configurable retention window. Never remove an object referenced by an active or posted bill.

### FR-07: Bill preview

Generate the preview using deterministic calculations.

Display:

- Invoice reference.
- Supplier.
- Firm/Company.
- Account where applicable.
- Each item, quantity, unit and rate.
- Item totals.
- Tax.
- Charges.
- Grand total.
- Paid amount.
- Outstanding balance.
- Due date.
- Proof-image attachment status.
- Newly created or unresolved master references.

Do not represent an unverified amount as an authoritative ERPNext total.

ERPNext can apply tax templates, rounding rules, UOM conversion and other accounting logic. Where its resulting totals differ from the ShopOS preview, require review rather than silently posting.

Buttons:

```text
[ Confirm & Save ] [ Edit ]
```

Set the state to `AWAITING_CONFIRMATION` after persisting the validated preview.

Confirmation callbacks must contain a stable draft identifier and revision or a server-side token resolving to them.

### FR-08: Confirm and save to ERPNext

On confirmation:

1. Verify Telegram identity and permissions.
2. Verify ownership of the draft.
3. Verify confirmation revision.
4. Revalidate mandatory information.
5. Lock the draft for posting using a SQLite transaction.
6. Establish a stable posting operation ID.
7. Check for an existing ERPNext document linked to the source draft.
8. Validate ERPNext master references.
9. Build the Purchase Invoice payload.
10. Create an ERPNext Purchase Invoice with `docstatus = 0`.
11. Persist the returned ERPNext invoice ID.
12. Verify the ERPNext document can be read.
13. Set local state to `COMPLETED`.
14. Notify the employee.

Use ERPNext's standard document resource API for draft creation.

**Do not invoke Submit in this release.**

ERPNext invoice submission affects accounting and may affect stock, depending on configuration. It must remain a separately controlled financial action.

A successful ERPNext API response should be followed by reconciliation and durable local recording before temporary draft data is deleted.

### FR-09: Idempotency and recovery

A single Telegram confirmation must never produce multiple ERPNext invoices.

Implement:

- Unique `source_draft_id`.
- Stable posting operation ID.
- Local SQLite transaction to claim posting.
- Database uniqueness constraints for local posting records.
- Reconciliation before every retry.
- Recovery after network timeouts.
- Recovery after worker crashes.
- Duplicate callback protection.

**Important limitation:** A local SQLite unique constraint cannot guarantee exactly-once creation in a remote ERPNext database.

Use an authoritative unique intake identifier on the ERPNext side, preferably a unique custom field or a small idempotent Frappe endpoint that checks and creates atomically.

If such ERPNext customization is unavailable, do not automatically repeat an uncertain create request. Mark it `RECONCILE_REQUIRED`, search for the existing document, and require review if its existence cannot be established.

Local state and ERPNext are separate transactional systems; there is no atomic transaction spanning both.

### FR-10: Failure handling

| Failure | Expected behavior |
|---|---|
| OpenRouter timeout | Preserve draft; offer retry |
| Invalid LLM output | Reject extraction; preserve draft |
| Missing supplier | Request clarification |
| Invalid item | Request correction |
| S3 upload failure | Preserve draft; allow retry |
| ERPNext unavailable | Keep posting operation recoverable |
| ERPNext validation error | Return to correctable state |
| ERPNext create timeout | Reconcile before retry |
| Process restart | Resume persisted state |
| Duplicate callback | Return existing status |
| Old confirmation button | Reject stale revision |
| User cancellation while posting | Prevent unsafe deletion |

Classify failures as transient, correctable or uncertain.

Retry transient failures with bounded exponential backoff.

Never blindly retry financial writes.

### FR-11: Completion and cleanup

A bill is `COMPLETED` only when the corresponding ERPNext invoice has been identified and the local posting result is durably stored.

On completion:

- Keep intake ID → ERPNext invoice ID mapping.
- Keep posting status and required audit metadata.
- Retain proof-image references.
- Delete unnecessary LLM conversation payloads.
- Delete temporary staging files.
- Delete the completed draft payload after confirming its posting record is durable.

Preserve financial audit records according to applicable business and regulatory retention requirements.

A failed or uncertain posting must not be removed by draft expiration cleanup.

---

## 5. Workflow state machine

Use these states:

```text
COLLECTING
    |
    v
VALIDATING
    |
    +---- missing/ambiguous --> NEEDS_INPUT
    |                              |
    |                              v
    |                          COLLECTING
    |
    v
AWAITING_CONFIRMATION
    |
    +---- Edit -------------> COLLECTING
    |
    +---- Confirm
    |
    v
POSTING
    |
    +---- correctable error -> NEEDS_INPUT
    |
    +---- uncertain result -> RECONCILE_REQUIRED
    |
    +---- verified success
    |
    v
COMPLETED
```

Terminal or exceptional states:

- `CANCELLED`
- `EXPIRED`
- `RECONCILE_REQUIRED`

Existing `COMMITTING` can be migrated or treated as the legacy equivalent of `POSTING`. Migration must preserve in-progress operations.

### State machine implementation

Use an explicit transition function in Python.

Each transition must:

- Validate source state.
- Validate requested action.
- Validate user authorization.
- Check draft revision.
- Persist the new state.
- Return the next action for the Telegram handler.

Never rely solely on in-memory FSM state for business-critical progress.

---

## 6. Database changes

Preserve existing tables.

Add minimal tables or fields through forward-only migrations.

### 6.1 Draft additions

Extend `bill_drafts` as needed:

```text
revision
last_error
erpnext_supplier_id
erpnext_company_id
s3_object_key
posting_operation_id
updated_at
```

Prefer reusing existing draft JSON fields when appropriate instead of duplicating every field in SQL columns.

### 6.2 ERPNext posting records

New table: `erp_postings`

```text
id
source_draft_id UNIQUE
operation_id UNIQUE
status
erpnext_doctype
erpnext_document_name
attempt_count
last_error
created_at
updated_at
completed_at
```

This record must survive completion and draft cleanup.

### 6.3 Master-data mappings

New table, only if necessary: `erp_entity_mappings`

```text
entity_type
local_entity_id
erpnext_doctype
erpnext_document_name
verified_at
```

Enforce uniqueness on local entity type/ID and relevant verified external mappings.

Do not use similarity matching as proof of entity identity.

### 6.4 Proof metadata

Add a `bill_proofs` table if the existing draft structure cannot safely represent upload status and multiple image versions.

Avoid adding the table unnecessarily for a single-proof MVP.

### 6.5 Database safety

- Use SQLite WAL mode where suitable.
- Enable foreign keys.
- Use appropriate busy timeouts.
- Use transactions for state transitions.
- Maintain one application instance initially.
- Apply migrations before polling starts.
- Use the SQLite backup API or another consistent backup mechanism rather than copying an active database file without coordination.

---

## 7. ERPNext integration

Create a small, independently testable adapter.

Suggested methods:

```python
class ERPNextClient:
    async def get_supplier(self, name): ...
    async def search_suppliers(self, query): ...
    async def get_company(self, name): ...
    async def get_item(self, item_code): ...
    async def search_items(self, query): ...
    async def get_purchase_invoice(self, name): ...
    async def find_invoice_by_source_id(self, source_id): ...
    async def create_purchase_invoice_draft(self, payload): ...
```

### API responsibilities

- Authenticate using an ERPNext API user with minimum necessary permissions.
- Apply request timeouts.
- Validate response schemas.
- Distinguish retryable errors from validation errors.
- Avoid logging credentials.
- Avoid returning raw ERPNext stack traces to Telegram users.
- Reuse HTTP connections.
- Support a mock adapter for tests.

### Purchase Invoice mapping

| ShopOS field | ERPNext |
|---|---|
| Vendor | Supplier |
| Firm | Company |
| Invoice number | Supplier invoice reference when applicable |
| Invoice date | Supplier invoice date |
| Items | Purchase Invoice Item rows |
| Quantity | Qty |
| Price | Rate |
| Due date | Due Date/payment schedule as configured |
| Taxes | ERPNext taxes/charges configuration |
| Charges | Appropriate ERPNext charge rows |
| Proof image | Private attachment or linked storage reference |
| Draft ID | Unique source-intake identifier |

Do not directly copy ShopOS's paid amount into an arbitrary ERPNext field and assume it creates a payment.

Recorded payments must eventually use ERPNext's supported Payment Entry or reconciliation workflow. In the first release, carry legacy payment information as clearly identified intake metadata until payment mapping has been designed and approved.

Validate the Purchase Invoice amount and tax interpretation against ERPNext's own calculations.

### ERPNext setup prerequisites

Before enabling posting, configure:

- ERPNext Company.
- Chart of accounts.
- Supplier masters.
- Item masters.
- Stock UOMs.
- Relevant Warehouses.
- Expense and payable account defaults.
- Tax templates and India localization as needed.
- Service account and permissions.
- Unique intake ID mapping.

The initial release should not silently manufacture missing ERP masters.

---

## 8. S3-compatible storage

Use an S3-compatible SDK such as boto3.

Required configuration:

```dotenv
S3_ENDPOINT_URL=
S3_REGION=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PREFIX=shopos/parchi
```

Storage interface:

```python
class ProofStorage:
    async def stage(...): ...
    async def finalize(...): ...
    async def get_reference(...): ...
    async def cleanup(...): ...
```

Preserve the existing service contract where practical.

An S3 upload cannot participate in a SQLite or ERPNext transaction.

Therefore, use durable object states and cleanup/reconciliation rather than attempting a cross-system rollback.

Original proof images must remain linked to their completed ERPNext invoices.

---

## 9. Telegram interactions

### Normal flow

```text
Employee: /upload_bill

Bot: New bill started.
     Draft: BILL-123

Employee: Gupta Traders
          5kg haldi 200/kg
          due in 10 days

Bot: Please attach the bill image.

Employee: [Image]

Bot: Bill preview
     Supplier: Gupta Traders
     Haldi: 5kg × ₹200
     Total: ₹1000

     [Confirm & Save] [Edit]

Employee: [Confirm & Save]

Bot: Saved to ERPNext.
     Invoice: PINV-00045
     Status: Draft
```

### Missing-field flow

```text
Bot: Which account/company should this bill use?

Employee: ShopOS

Bot: Company selected.
     Remaining: proof image
```

### Correction flow

```text
Employee: Change haldi to 6kg

Bot: Updated.
     Haldi: 6kg × ₹200
     Total: ₹1200

     [Confirm & Save] [Edit]
```

### ERPNext failure flow

```text
Bot: Bill is saved locally but ERPNext
     confirmation is pending.

     Draft: BILL-123
     Status: Reconciliation required
```

Never claim success until the ERPNext document has been identified.

---

## 10. Hosting and deployment

### Railway

Deploy one continuously running Python service.

Start command:

```bash
uv run python -m shopos.main
```

Mount a persistent volume and set:

```dotenv
DATABASE_PATH=/data/shop.db
```

The volume directory must exist and be writable.

Do not run multiple polling replicas against the same bot token or SQLite file.

### ERPNext

Use a managed ERPNext environment, preferably Frappe Cloud.

Store the base URL and API credentials in Railway environment secrets.

### Storage

Use a private S3-compatible bucket with explicit retention and backup policies.

### Configuration additions

```dotenv
ERPNext_BASE_URL=
ERPNext_API_KEY=
ERPNext_API_SECRET=
ERPNext_TIMEOUT_SECONDS=20

S3_ENDPOINT_URL=
S3_REGION=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PREFIX=shopos/parchi

DATABASE_PATH=/data/shop.db
ERP_POSTING_ENABLED=false
PROOF_STORAGE_BACKEND=local
```

All existing environment variables remain supported.

New settings should have safe development defaults where feasible, while production posting must fail clearly if mandatory credentials or mappings are absent.

Use a feature flag to enable ERPNext posting only after verification.

---

## 11. Reliability and security

### Reliability

- Persist changes before acknowledging them.
- Never drop drafts on external API failure.
- Restore valid work after process restart.
- Use stable IDs for external writes.
- Reconcile uncertain ERPNext responses.
- Reject stale confirmation callbacks.
- Keep failed operations visible in `/status`.
- Prevent overlapping state transitions for the same draft.
- Preserve existing local bill data during migration.

### Security

- Preserve Telegram allowlist middleware.
- Verify user access on callbacks, not only incoming messages.
- Enforce authorization for financial operations.
- Use least-privilege ERPNext credentials.
- Store secrets only in environment variables or a secret manager.
- Encrypt external connections in transit.
- Keep S3 objects private.
- Validate image size, type and content.
- Avoid exposing raw invoice images through permanent public links.
- Avoid logging unnecessary personal or financial information.
- Use appropriate data-retention and deletion policies.

### Observability

Use structured logs with:

```text
draft_id
telegram_user_id
operation_id
state
service
duration_ms
error_code
```

Never log API keys, full proof-image content or unnecessary sensitive payloads.

Provide a startup reconciliation pass for recoverable posting operations.

---

## 12. Implementation phases

### Phase 0 — Repository audit

**Goal:** Establish the actual current state.

Tasks:

- Inspect existing modules.
- Read all migrations.
- Run current tests.
- Document current behavior.
- Identify local database dependencies.
- Verify the confirm/cancel paths.
- Identify backward-compatibility risks.

Deliverables:

- Repository audit.
- Baseline test results.
- Minimal change plan.

No production code changes in this phase.

### Phase 1 — Explicit draft states

**Goal:** Make current draft processing recoverable.

Tasks:

- Introduce explicit state transitions.
- Implement `AWAITING_CONFIRMATION`.
- Add revision handling.
- Reject stale buttons.
- Preserve drafts across restarts.
- Prevent expiration cleanup from deleting active posting records.

Acceptance: A draft can survive a restart at every nonterminal state.

### Phase 2 — S3 proof storage

**Goal:** Remove permanent dependency on local proof-image storage.

Tasks:

- Add S3 backend.
- Keep local backend for tests.
- Upload images privately.
- Store object keys.
- Implement replacement and cleanup.
- Test upload failure and recovery.

Acceptance: A bill image remains retrievable after Railway application redeployment and local staging cleanup.

### Phase 3 — ERPNext read integration

**Goal:** Resolve authoritative master records.

Tasks:

- Add ERPNext API client.
- Implement supplier lookup.
- Implement company lookup.
- Implement item lookup.
- Map legacy account and item IDs.
- Reject ambiguous matches.
- Test with a sandbox ERPNext instance.

Acceptance: Existing supplier/item references resolve accurately without creating duplicate masters.

### Phase 4 — ERPNext draft posting

**Goal:** Create exactly one recoverable ERPNext draft per intake.

Tasks:

- Implement invoice payload mapper.
- Implement posting operation record.
- Introduce unique source intake mapping.
- Implement pre-write duplicate reconciliation.
- Create Purchase Invoice drafts.
- Verify created documents.
- Store ERPNext document IDs.
- Update completion and cleanup.

Acceptance: Confirmation creates one ERPNext draft with correct supplier, company, items, amounts and proof reference.

### Phase 5 — Failure and recovery testing

Test:

- Restart during extraction.
- Restart during S3 upload.
- Restart while awaiting confirmation.
- Restart during ERPNext posting.
- Timeout after successful remote creation.
- Multiple confirmation clicks.
- Stale preview revisions.
- ERPNext authentication failure.
- Missing ERPNext master data.
- Incorrect accounting defaults.
- Cancellation while posting.
- Draft expiration during recovery.

Acceptance: No lost confirmed bills and no duplicate ERPNext invoices in the tested failure scenarios.

### Phase 6 — Deployment and cutover

Tasks:

- Back up the existing SQLite database.
- Deploy to Railway.
- Mount the SQLite volume.
- Configure S3 credentials.
- Configure ERPNext credentials.
- Verify an end-to-end test invoice.
- Compare mapped amounts with ERPNext.
- Enable posting for selected allowed users.
- Monitor posting and reconciliation errors.
- Preserve rollback capability.

Do not delete the old local-bill implementation until production parity and data migration are explicitly approved.

---

## 13. Testing strategy

### Unit tests

- Draft transitions.
- Extraction merging.
- Required-field validation.
- Entity matching.
- Money calculations.
- Invoice payload mapping.
- Revision checks.
- Idempotency decisions.

### Integration tests

- OpenRouter with mocked and recorded responses.
- S3-compatible storage with test bucket or emulator.
- ERPNext API with mocked HTTP responses.
- Sandbox ERPNext invoice creation.
- SQLite migrations and recovery.

### End-to-end tests

- Enter and confirm a valid bill.
- Enter an incomplete bill.
- Correct existing items.
- Replace proof image.
- Resume after restart.
- Retry after network failure.
- Handle duplicate confirmation.
- Reconcile an uncertain posting.

### Mandatory invariants

1. One draft can map to at most one ERPNext Purchase Invoice.
2. No LLM output directly performs database operations.
3. No unconfirmed draft is posted.
4. No changed revision is confirmed using an older button.
5. No completed bill loses its ERPNext document mapping.
6. No external API error silently destroys the draft.
7. `pricebot/` remains unaffected.

---

## 14. Definition of done

The project is complete when:

- Existing Telegram commands work.
- Existing OpenRouter extraction behavior is preserved.
- Incremental corrections work reliably.
- Drafts survive application restarts.
- S3 images are stored privately and referenced correctly.
- ERPNext suppliers and items resolve correctly.
- Every successful confirmation creates one recoverable ERPNext Purchase Invoice draft.
- Duplicate requests cannot silently generate duplicate invoices.
- ERPNext failures are visible and recoverable.
- All previously passing tests remain passing.
- New unit, integration and recovery tests pass.
- Production credentials are not committed to the repository.
- Deployment and rollback procedures are documented.
- The complete Telegram-to-ERPNext flow is verified against a sandbox instance.

---

## 15. Engineering constraints for Codex

Follow these rules throughout implementation:

- Explicit is better than implicit.
- Simple is better than complex.
- Readability counts.
- Prefer extending existing services.
- Do not introduce new infrastructure without a demonstrated requirement.
- Do not create abstractions with only one speculative use case.
- Keep external services behind small interfaces.
- Errors must never pass silently.
- Every financial write must be auditable.
- Avoid premature optimization.
- Use migrations rather than destructive schema replacement.
- Keep `pricebot/` unchanged.
- Keep tests green after each phase.
- Never modify production ERPNext data during development tests.
- Report unverified assumptions and incomplete work.

**Final implementation principle:**

ShopOS owns the conversation and ingestion state.

ERPNext owns validated financial and inventory records.

S3 owns the original images.

The integration between them must be explicit, recoverable and simple enough for a single developer to maintain.
