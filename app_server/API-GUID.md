
# ShopOS Bill Creator — Backend API Creation Guide

## 1. Goal and scope

Build a minimal, fast, async FastAPI service over PostgreSQL for a Kotlin/Compose Android bill-ingestion app. Vendors and items are downloaded as compact catalogs once per app session, filtered locally while typing, and refreshed when changed. Bill creation remains server-authoritative and atomic.

**Stack:** Python 3.12+, FastAPI, asyncpg, PostgreSQL 14+, Uvicorn, Android Retrofit.

**Out of scope for v1:** ORM, Redis, WebSockets, search-as-you-type API calls, invoice OCR, document upload, editing/deleting bills, accounting workflows.

## 2. Project files

```text
backend/
├── main.py                   # FastAPI, Pydantic schemas, routes, lifespan
├── db.py                     # asyncpg pool; fetch_one, fetch_all, execute(transaction)
├── pyproject.toml            # fastapi, uvicorn, asyncpg
├── 001_create_purchase_bills.sql
└── README.md
```

Keep API code in `main.py` until it becomes difficult to navigate. Use parameterized SQL. Do not add a framework layer without need.

## 3. PostgreSQL model (existing migration)

| Table | Fields | Rules |
|---|---|---|
| `vendors` | `id`, `name`, `address`, `phone_number` | `name` required; address and phone optional |
| `items` | `id`, `name`, `unit`, `purchase_price`, `sell_price` | Sell price optional; purchase/sell share the same unit |
| `bills` | `id`, `vendor_id`, `due_date`, `document_url`, `is_paid`, `paid_at`, `paid_amount`, `charges`, `tax`, `notes` | `is_paid` defaults false; charges/tax/notes optional |
| `bill_items` | `bill_id`, `line_number`, `item_id`, `quantity`, `purchase_unit_price`, computed `line_total` | Price snapshot for historical accuracy |
| `tags` | `id`, `name` | Unique name |
| `bill_tags` | `bill_id`, `tag_id` | Many-to-many; no duplicate pairs |

The `bill_totals` database view calculates subtotal, total and balance due. `NUMERIC`, not float, represents money. Price and money values are encoded as **decimal strings in JSON** to avoid floating-point rounding in Android. IDs are integers.

## 4. v1 HTTP endpoints

| Method | Route | Purpose | Status |
|---|---|---|---|
| `GET` | `/` | Service info | 200 |
| `GET` | `/health` | Database liveness | 200, or 503 if unavailable |
| `GET` | `/vendors` | Full compact vendor catalog | 200 |
| `POST` | `/vendors` | Create vendor from inline modal | 201 |
| `GET` | `/items` | Full compact item catalog | 200 |
| `POST` | `/items` | Create item from inline modal | 201 |
| `POST` | `/bills` | Create bill + lines + tags in one DB transaction | 201 |
| `GET` | `/bills/{bill_id}` | Fetch saved bill for confirmation | 200/404 |
| `GET` | `/docs` | Generated OpenAPI docs | 200 |

**Important change to existing starter:** `GET /vendors` and `GET /items` currently default to only ten records. Replace these autocomplete-style queries with full-catalog queries for the local-search design. For v1 (~300 items), a plain array is sufficient. Add pagination only when payloads become large. Avoid retaining stale `q`/`limit` logic in Android.

### GET /vendors

Response `200`:
```json
[
  {"id": 1, "name": "ABC Traders", "address": "Aligarh", "phone_number": null},
  {"id": 2, "name": "Sharma Suppliers", "address": null, "phone_number": "9876543210"}
]
```

### POST /vendors

Request:
```json
{"name": "New Vendor", "address": "Aligarh", "phone_number": null}
```

Response `201`:
```json
{"id": 3, "name": "New Vendor", "address": "Aligarh", "phone_number": null}
```

`name` required, trimmed and nonempty; address and phone optional. Return the new row so Android can add it to local state and **auto-select `id`**. Allow duplicate names only if business policy permits; do not silently merge suppliers by name.

### GET /items

Response `200`:
```json
[
  {"id": 10, "name": "Turmeric", "unit": "kg", "purchase_price": "160.00", "sell_price": "220.00"},
  {"id": 11, "name": "Cumin", "unit": "kg", "purchase_price": "450.00", "sell_price": null}
]
```

### POST /items

Request:
```json
{"name": "Black Pepper", "unit": "kg", "purchase_price": "600.00", "sell_price": null}
```

Response `201`: full saved item including server-generated `id`.

`name`, `unit` required; `purchase_price >= 0`; `sell_price` nullable. Store one shared unit on the catalog item. Auto-select newly created `id` in the bill form.

### POST /bills

Request:
```json
{
  "vendor_id": 3,
  "due_date": "2026-11-15",
  "document_url": "https://files.example.com/bills/invoice-123.jpg",
  "items": [
    {"item_id": 10, "quantity": "5.000", "purchase_unit_price": "159.50"},
    {"item_id": 11, "quantity": "2.000"}
  ],
  "charges": "40.00",
  "tax": "0.00",
  "notes": "October stock",
  "tags": "spices, wholesale",
  "paid_amount": "0.00"
}
```

`purchase_unit_price` can be omitted: server reads current catalog purchase price. If supplied, save override for **this bill only**, not on the catalog. At least one line is required. `charges`, `tax`, `notes` optional; `tags` may be empty string. `paid_amount` defaults to zero. Existing schema determines `is_paid` automatically: fully paid only when paid amount equals total and is greater than zero. For zero-total bills, clarify the business rule before allowing them to be marked paid.

Response `201` (illustrative):
```json
{
  "id": 1001,
  "vendor_id": 3,
  "due_date": "2026-11-15",
  "document_url": "https://files.example.com/bills/invoice-123.jpg",
  "is_paid": false,
  "paid_amount": "0.00",
  "subtotal": "1697.50",
  "total_amount": "1737.50",
  "balance_due": "1737.50"
}
```

The example above assumes the `Cumin` catalog price is `450.00`: `5 * 159.50 + 2 * 450.00 = 1697.50`.

### GET /bills/{bill_id}

Return bill metadata, the line items (including saved purchase price and quantity), and tags. Use one/few indexed queries; not one query per item. This route is useful for Android success confirmation and retrieving persisted data.

## 5. Data flow and Android behavior

```text
App starts / refresh required
    ├── GET /vendors ──┐
    └── GET /items ────┤
                       ▼
                 Kotlin StateFlow
                       │
          type → filter in memory
                       │
          ├── match → select ID
          └── + Add → popup → POST /vendors or /items
                                    │
                    append returned row to StateFlow
                                    │
                       auto-select returned ID
                       │
             submit → POST /bills
                       │
            one SQL transaction → 201
```

**Android local search:** normalize query and names with `trim()` and case-folding; use `contains()` for natural match behavior. For hundreds of entries it is instant. Display a stable `+ Add Vendor` / `+ Add Item` action at the bottom regardless of result count. Search should never make one API call per keystroke.

**Refresh policy:** initial app launch, manual refresh, after a catalog create, and when resuming after a configurable interval (example: 5 minutes). Re-fetch on `401`/`403` only after authentication is restored; do not treat these as data refresh signals. If network is unavailable, show cached suggestions but disable saving until online. An in-memory-only cache is lost when the process is killed; a future Room cache can support persisted offline search.

**Multi-device note:** caches can be stale. Server must verify vendor and item IDs and never trust client catalog prices as canonical. App should offer refresh on a missing record. Concurrent updates are handled by server-side validation, not by forcing a full app reload on every tap.

## 6. Database and transaction rules

1. Create one `asyncpg` connection pool in FastAPI lifespan. Close on shutdown.
2. `db.fetch_one` and `db.fetch_all` accept query plus positional parameters (`$1`, `$2`).
3. `db.execute(callback)` gets one connection and wraps the callback in a single transaction.
4. `POST /bills`: check vendor; resolve all item catalog prices; compute amount using `Decimal`; reject payment above total; insert bill; insert all lines; upsert tags; attach bill/tag pairs; return totals. **Rollback everything on error.**
5. Never interpolate user text into SQL. Always pass parameters.
6. Do not recompute historical bills using current `items.purchase_price`; use saved `bill_items.purchase_unit_price`.
7. Use appropriate SQL constraints and indexes; `bills.vendor_id`, `bill_items.item_id`, and `bill_tags.tag_id` are indexed in the existing migration.
8. For full catalog queries, `ORDER BY lower(name), id` yields stable user-visible ordering. A name-based index is optional until catalog size justifies it.

## 7. Validation and errors

| Situation | Response |
|---|---|
| Missing/invalid required fields | `422` with Pydantic validation details |
| Vendor/item ID does not exist | `404` |
| Conflict such as a rejected duplicate | `409` |
| Paid amount exceeds total | `422` |
| Database unavailable | `503` (health), controlled `5xx` for other routes |

Apply sane max lengths (`name` ≤200, unit ≤50, tags ≤100 each), max 200 bill lines, nonnegative money, and strictly positive quantity. Decide whether URLs must be HTTPS in deployment and whether document links can expire; storing a stable storage key is safer than persisting short-lived signed URLs.

## 8. Implementation sequence

- [ ] Apply/verify SQL migration. Check `\dt` and `\dv` in `psql`.
- [ ] Implement async connection pool in `db.py`; read `DATABASE_URL` from env.
- [ ] Define Pydantic input models in `main.py`.
- [ ] Implement full-catalog GET routes (no 10-result search limit).
- [ ] Implement POST vendor/item returning new rows.
- [ ] Implement transactional POST bill.
- [ ] Implement GET bill by ID.
- [ ] Add health endpoint and OpenAPI docs.
- [ ] Test invalid IDs, empty bill, missing items, partial payment, duplicate tags, and rollback.
- [ ] Test two Android clients: create in client A, refresh in B.

## 9. Run locally

```bash
cd backend
export DATABASE_URL='postgresql://localhost:5432/shopos'
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

On Android emulator, API base URL is usually `http://10.0.2.2:8000/` for a backend running on your development machine. On a physical device use the machine's reachable LAN address, and ensure network/firewall permissions allow access. Use HTTPS for any externally reachable deployment.

Check `http://localhost:8000/docs`; try GET `/vendors`, POST `/vendors`, GET `/items`, POST `/items`, then POST `/bills`.

## 10. Production minimums

- Add authentication and authorization **before** exposing API outside trusted development networks.
- Require HTTPS, restrict CORS (Android native apps are not controlled by CORS), and limit request sizes.
- Add a client-generated `Idempotency-Key` or unique client bill UUID before real multi-device use: a retry following a timeout must not create the same bill twice.
- Use restricted database credentials and backups; do not run as a superuser.
- Add structured logs and a real health/readiness signal; do not log sensitive document URLs or raw customer details.

**Definition of done:** Android can search catalogs offline within one open session, add and auto-select vendor/item, save a multi-item bill exactly once, and receive stable totals from PostgreSQL. No per-keystroke backend requests.
