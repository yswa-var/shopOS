
Project Requirements Document

Goal: Build a small, reliable, AI-assisted Telegram bot that collects purchase bills through natural conversation, validates them, saves bill proof images locally, and inserts completed bills into SQLite.

1. Non-negotiable requirements
Ingest bills only. No analytics, payment reminders, ERP, stock updates or OCR.
Accept Hindi, Hinglish and English text.
Accept a required JPEG/PNG image as proof.
Support incomplete bills across multiple Telegram messages.
Repeatedly ask for missing or ambiguous information without losing previous inputs.
Use OpenRouter exclusively for language understanding.
Use deterministic Python for SQL, money, IDs, validation and persistence.
Require explicit human confirmation before saving a bill.
Delete temporary draft state after successful completion or cancellation.
Survive application restarts without losing incomplete bills.
No FastAPI, Redis, Docker, Temporal, LangGraph, webhooks or exposed ports.
Architecure 

```
Staff (Telegram private chat)
            |
            v
     aiogram long polling
            |
            v
       Message Router
       /           \
     Text          Image
      |              |
      v              v
  OpenRouter     Local image
  extraction      staging
      |              |
      +-------+------+
              |
              v
       Draft Manager
       SQLite draft row
              |
              v
       Entity Resolver
     vendor/account/item
              |
              v
      Validation Engine
              |
         Missing?
         /           \
       Yes        No
        |             |
      ask_user  v
        |        Bill Preview
        |        Confirm/Edit
        |             |
        +----<----+
                  |
             Confirmed
                  |
                  v
         SQLite transaction
                  |
                  v
         Finalize image path
                  |
                  v
        Delete temporary state
                  |
                  v
         Telegram receipt
```
User interaction specification
Scenario A — Complete information
Staff
ABC Traders se 10kg haldi 180/kg aur 5kg jeera 250/kg, Firm A. ₹500 paid, due 15 Nov.
parchi.jpg attached

```
Bill ready for confirmation
Vendor: ABC Traders
Account: Firm A ·
Item
Qty
Amount
Haldi
10 kg
₹1,800
Jeera
5 kg
₹1,250

Total
₹3,050
Paid
₹500
Due
₹2,550
Due date: 15 November 2026
Proof: Received
Confirm & Save
Edit
```

Scenario B — Missing information
User sends:
10kg haldi 180/kg, 500 paid, due 15 Nov
Bot responds with everything understood:
Draft bill
Haldi: 10 kg × ₹180 = ₹1,800
Paid: ₹500 · Due: ₹1,300
Due date: 15 November
Missing: Vendor, Account, Bill proof image.
Send the missing details.
User replies:
ABC Traders, Firm B FY26
The bot merges the newly extracted details with the existing draft. It must not reset the item, quantity, amount or due date.
Bot then requests only the missing proof image.
 

Scenario C — Corrections
User says:
Haldi 10 nahi 12kg karo
OpenRouter extracts the correction. Python updates the corresponding draft item and recalculates the amount. The bot presents the new summary.

Scenario D — Unknown vendor or item
If ABC Traders is not found, the bot must ask whether the user wants to create it. For a new vendor, obtain its name, address and 10-digit phone number.
New vendor/item/account creation is provisional in the draft. Actual database inserts happen only after final bill confirmation, in the same transaction.
Database specification
items (
    id INTEGER PRIMARY KEY,
    item_name TEXT NOT NULL,
    purchase_unit TEXT,
    purchase_unit_price float,
    sell_unit TEXT,
    sell_price float,
    supplier TEXT,
    date_purchased TEXT,
    date_modified TEXT
);
vendors
id TEXT PK, name TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL, created_at, updated_at
accounts
id TEXT PK, account_name TEXT NOT NULL, firm_name TEXT NOT NULL, 

bills
id TEXT PK, invoice_number TEXT NOT NULL, proof TEXT NOT NULL, vendor_id TEXT FK, account_id TEXT FK, tax float, charges float, total float, paid float, due float, due_at, paid_at, created_at, updated_at, created_by
bill_items
id TEXT PK, bill_id TEXT FK, item_id INTEGER FK, quantity INTEGER, unit_price float, line_total float

Additional constraints:
UUIDs generated in Python for new record IDs.
vendors.phone must contain exactly ten digits.
Date/time values stored as ISO-8601 strings.
Timestamps generated using asia/india/kolkata configured timezone.
proof stores the relative path to the image file.
Foreign key enforcement enabled for every connection.
Nonnegative monetary values and positive quantities.
Index foreign keys and invoice lookup fields.
Prevent duplicate invoices within the appropriate vendor/account/same day/ same amount/ same number of lineitems. scope.
If a bill is fully paid, populate paid_at on confirmation; otherwise leave null.
Payments are recorded only as the amount entered at ingestion. No payment ledger in v1.
Temporary draft table

CREATE TABLE bill_drafts (
    draft_id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL UNIQUE,
    state TEXT NOT NULL,
    draft_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

Persist all conversation state here; do not rely on aiogram's volatile MemoryStorage

State values:
COLLECTING
AWAITING_CONFIRMATION
COMMITTING

One active draft per Telegram user Completed and cancelled drafts are deleted.

{
  "invoice_number": "INV-26-001",
  "proof": "parchi/2026-10-28/173045_ab12.jpg",
  "vendor_id": "vendor-uuid",
  "account_id": "account-uuid",
  "items": [
    {
      "item_id": 123,
      "no_units": "10",
      "unit_price": "180.00"
    }
  ],
  "tax": "0.00",
  "charges": "50.00",
  "paid_balance": "500.00",
  "due_at": "2026-11-15"
}

Defaults: tax, charges and paid amount are zero. Invoice number is generated in Python and may be edited. Vendor, account, items, quantity, unit price, due date and proof are mandatory.

OpenRouter integration
Responsibility
OpenRouter is a structured information extractor, not an autonomous database agent
Input:
{
  "current_draft": {
    "vendor_name": null,
    "account_name": null,
    "items": [
      {"name": "haldi", "quantity": "10", "unit": "kg"}
    ]
  },
  "latest_message": "ABC Traders, Firm B FY26"
}
Expected extraction:
{
  "vendor_name": "ABC Traders",
  "account_name": "Firm B",
  "fyear": 26,
  "item_changes": [],
  "intent": "update_draft"
}

Model configuration
Use OpenRouter's OpenAI-compatible endpoint with a configurable model supporting JSON Schema structured outputs. Strict-schema availability depends on the model/provider endpoint.
GitHub
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

Implementation rules:
Define extraction schemas with Pydantic.
Pass only the current relevant draft and latest message.
Extract field updates, not an entirely new bill each turn.
Use an explicit list of operations for item additions, updates and removals.
Set LLM request timeout and bounded retries.
On invalid JSON, failed schema validation or provider errors, ask the user to retry; keep the draft intact.
Never send proof images to OpenRouter.
Do not store complete LLM transcripts.
Never send API keys, database contents or unrelated user information to the model.
Ignore any model-generated instruction to execute SQL, manipulate files or bypass confirmation.
Entity resolution
Python resolves names against SQLite.

Search string vie normalised part string search (if 1 match found case {Exact match} if multiple/none then {do sequenced string similarity search}) 
In similarity search (if similarity >90% and only 1 found then case {Exact match} else case {Multiple matches} )

In case of {Multiple matches} do a union of part string search and similarity search,
 The union set: if 0 matches then create new item/account/vendor else ask user to choose one. 



Situation
Required behavior
Exact unique vendor match
Use its ID
Multiple vendor matches
Ask user to choose
Unknown vendor
Offer creation and request missing vendor fields
Account found, matching firm
Use its ID
Unknown account
Collect account name, firm name (similariy search)
Exact unique item match
Use existing item ID
Ambiguous item
Ask user to select
Unknown item
Collect required item data and stage creation


Item creation uses items schema. Collect at minimum item name, purchase unit and purchase unit price. Optional catalog fields remain nullable

Image proof specification
File layout
data/
├── shop.db
├── parchi/
│   └── 2026-10-28/
│       └── 173045_ab12.jpeg
└── staging/
    └── <draft_uuid>.jpg

Requirements:
Proof image is mandatory before confirmation.
Accept Telegram photos and documents of any file type as proof.
Do not perform OCR, resize, compress or analyze images.
Download using the Telegram Bot API.
Validate that the downloaded proof is non-empty and within the configured size limit.
Maximum file size: configure to 10 MB
Generate safe filenames; never trust a user-supplied path.
Normalize storage extension to a safe extension or use `.bin` when unavailable.
Save the image first under data/staging/.
At confirmation, move it into data/parchi/YYYY-MM-DD/.
Persist the relative final path in bills.proof.
If an image is replaced before confirmation, remove the older staged image.
Never delete a finalized proof as part of draft cleanup.


Crash-safe image handling
Filesystem moves and SQLite transactions are not one atomic operation.
Implement a recoverable commit sequence:
Validate draft, image and all references.
Enter COMMITTING and persist that state.
Copy or move the proof to its unique final path.
Insert bill, bill items and any newly created references in one database transaction.
Delete the draft on successful commit.
On recovery, detect incomplete commits and reconcile image/database state without duplicating bills.
Use draft_id as a unique source reference in the committed bill so retries can identify an already saved bill.
Never report success until the committed bill and its proof file both exist


Event > Draft handling
First message > Create draft if none exists; otherwise resume
New text > Extract and merge
New image > Update proof reference
Missing information > Keep draft
Bot restart > Load existing draft from SQLite
User confirms > Commit bill, delete draft
/cancel > Delete draft and staged image
Validation failure > Keep draft and error string
Database write failure > error string



Storage optimizations:
No Redis.
No persisted chat history.
No stored LLM responses beyond merged draft fields.
No duplicate image copies after commit.
No permanent confirmation messages or FSM state.
Keep permanent invoices and proof images until separately authorized for deletion.
Cleanup must skip active COMMITTING records and reconcile them before removing any files.
Telegram command contract
Command/action
Behavior
/start
Show service purpose and instructions

/upload_bill    Start/resume bill entry
/status         Show current draft and missing fields
/cancel         Cancel draft and delete staged proof
Confirm & Save  Validate and commit
Edit            Return draft to collecting state
Replace Image   Wait for another image
Create Vendor   Collect missing vendor details
Create Item     Collect item fields
Create Account  Collect account fields
The bot operates in group chat and checks a configured allowlist of Telegram user IDs.
The confirmation callback must verify that it belongs to the user who owns the draft.
Operational requirements
Security
Secrets in .env, never committed to Git.
Explicit authorized Telegram user ID allowlist.
No arbitrary SQL or tool execution from LLM output.
Parameterized SQL statements only.
Validate all IDs and amounts server-side.
Keep database and proof directories outside the public web root.
Restrict local filesystem permissions.
Reliability
Process one user's draft updates sequentially.
SQLite transactions for every mutation.
Unique submission/draft IDs to prevent duplicate commits.
One running polling instance for the bot token.
On startup, recover incomplete commits and clean expired drafts.
Recover gracefully from OpenRouter timeouts, Telegram download failures and interrupted database writes.
Use a stable configured business timezone, e.g. Asia/Kolkata.
Backup
Drafts are temporary; confirmed bills and images are permanent business records.
parchi-bot/
├── pyproject.toml
├── uv.lock
├── price_bot
├── .env.example
├── .gitignore
├── README.md
├── PRD.md
├── AGENTS.md
│
├── src/shopos/
│   ├── main.py
│   ├── config.py
│   │
│   ├── bot/
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── middleware.py
│   │
│   ├── llm/
│   │   ├── client.py
│   │   ├── extractor.py
│   │   └── schemas.py
│   │
│   ├── services/
│   │   ├── draft_service.py
│   │   ├── bill_service.py
│   │   ├── entity_resolver.py
│   │   ├── validator.py
│   │   └── proof_storage.py
│   │
│   └── db/
│       ├── connection.py
│       ├── migrations.py
│       └── repository.py
│
├── tests/
│   ├── test_extraction.py
│   ├── test_drafts.py
│   ├── test_validation.py
│   ├── test_bills.py
│   ├── test_proof_storage.py
│   └── test_recovery.py
│
└── data/
    ├── shop.db
    ├── staging/
    └── parchi/

.env structure 
```
TELEGRAM_BOT_TOKEN=9xxxxxx7:AxxxxxxxxxxxxxxxxxxI
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
BUSINESS_TIMEZONE=Asia/Kolkata
ALLOWED_TELEGRAM_USER_IDS=0000013,9400003 or 90000013
MAX_IMAGE_MB=10
LOG_LEVEL=INFO
```

## Implementation roadmap — Codex quests
```
01
Bootstrap
Runnable Python package, configuration, /start, /upload_bill and /cancel.
Acceptance: Bot starts and polls Telegram without HTTP hosting.

02
Database
SQLite migrations, existing items compatibility, vendors/accounts/bills/bill_items and repository.
Acceptance: Foreign keys, constraints, transaction rollback and schema migrations pass.

03
Draft state
Persistent drafts, merge, resume, expiry and cleanup.
Acceptance: Restart midway, recover the draft and delete it after cancellation.

04
OpenRouter
Typed extraction, corrections, validation of model outputs and errors.
Acceptance: Hindi/Hinglish inputs parsed; missing fields never fabricated.

05
Proof storage
Download, validate, stage, replace and finalize images.
Acceptance: Invalid, oversized and interrupted image downloads handled safely.

06
Bill entry
Vendor/account/item resolution and missing-field dialogue.
Acceptance: Existing and unknown entities handled correctly.

07
Confirmation
Preview, edits, final validation, atomic commit and Telegram receipt.
Acceptance: Repeat confirmation creates only one bill.

08
Hardening
Recovery, permissions, cleanup, logging, startup scripts, backup and documentation.
Acceptance: Crash, restart, concurrency and recovery tests pass.
```

Release checklist
0/20

[ ] Complete bill with image saves successfully
[ ] Text arrives before image
[ ] Image arrives before text
[ ] Photo caption contains bill details
[ ] Vendor/account/item missing triggers clarification
[ ] Multi-turn replies preserve previous values
[ ] User correction updates only intended fields
[ ] Unknown vendor creation collects address and phone
[ ] Ambiguous item requires user selection
[ ] Duplicate invoice is rejected
[ ] Negative values and overpayment are rejected
[ ] Missing proof blocks confirmation
[ ] App restart recovers incomplete draft
[ ] Cancelled draft and staged proof are deleted
[ ] Expired draft is safely removed
[ ] OpenRouter timeout does not erase state
[ ] Duplicate confirmation does not duplicate bill
[ ] Crash during commit recovers without losing proof
[ ] Unauthorized user cannot submit
[ ] Confirmed bill and proof survive cleanup
