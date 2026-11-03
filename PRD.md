# ShopOS — Product Requirements

## Goal
Let a shop employee record a supplier purchase with proof quickly, then find that record later. The owner controls employee access. The app should feel effortless under busy shop conditions.

## People and access
- **Employee:** sign in with an individual account; create bills; query bills allowed by server policy.
- **Owner:** all employee actions plus user/permission management and audit access.
- Every saved bill records its creator and timestamps. The backend checks permission on every operation.

## Main paths
1. **Ingest bill:** choose or quickly create vendor; add one or more items; enter quantity and whichever price information is available; optionally enter tax and charges; attach required proof photo; review and save.
2. **Query bills:** search and filter by vendor, item, date, amount, or employee; open bill detail and its proof photo.
3. **Owner controls:** create/deactivate employees and set permissions. These screens are hidden from ordinary employees and protected by backend authorization.

## Bill entry rules
- Searchable vendor and item selectors prioritize recent/frequent choices and support aliases.
- Create a vendor or item inline without abandoning the bill.
- Quantity, unit rate, and line amount recalculate from the latest edited price input:
  - quantity + amount => calculate rate;
  - quantity + rate => calculate amount;
  - changing quantity preserves the last entered pricing basis.
- Tax and charges are optional and separate from line amounts. Show the final payable total clearly.
- Reject non-positive quantity and invalid/negative money. Use decimal-safe calculations and defined rounding.
- Support multiple items per bill from the start.
- Proof photo is mandatory before final save. Upload privately; show Draft / Uploading / Saved states and allow safe retry.
- Prevent duplicate bills when a save is retried (client idempotency key + server uniqueness strategy).

## V1 non-goals
Inventory balances, sales/POS, payment accounting, OCR/AI extraction, analytics, offline bill submission, and multi-branch operations.

## Quality goals
- Keep common bill entry low-tap and numeric-keyboard friendly; measure with actual employees.
- Search catalogs locally for instant feedback; server remains authoritative.
- Preserve a recoverable local draft if the app closes mid-entry.
- Make loading, upload failure, validation failure, and saved state visible.
- Do not silently discard user input or failed writes.

## Data and privacy
- PostgreSQL is the shared source of truth.
- Store photo metadata and private object keys, not public bucket URLs.
- Keep audit events for creation, controlled corrections, deactivation, and permission changes.
- Automated tests use synthetic data only.

## Acceptance outline
- Staff can authenticate and only perform permitted actions.
- A user can create a vendor/item inline, enter a multi-item bill, see exact calculations, attach proof, and save once.
- A retry does not create a duplicate.
- A user can find and open a saved bill, subject to permissions.
- Owner can manage employees; non-owner API requests are rejected even if manually constructed.
- Draft survives process interruption and can be resumed.
