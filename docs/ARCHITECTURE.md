# Architecture boundaries

```text
Android (Compose)
  ├── presentation: screens and state holders
  ├── domain: bill rules, validation, use cases
  ├── data: API, Room draft/cache, repositories
  └── form: central field registry and reusable inputs
             │ HTTPS + per-employee token
             ▼
FastAPI modular monolith
  ├── auth and permission checks
  ├── catalog (vendors/items)
  ├── bills (validation, calculations, query)
  ├── attachments (signed private storage)
  └── audit
             │
             ▼
PostgreSQL (authoritative shared records)
```

## Boundaries
- Compose renders UI and collects input. It does not decide who is authorized or whether a bill is valid.
- Domain code owns calculation and validation rules that can be tested without Android or HTTP.
- Repositories hide local Room and network details from screens.
- FastAPI owns authorization, final validation, idempotency, and transactions.
- Passwords use salted PBKDF2 hashes. Opaque bearer tokens are stored only as SHA-256 hashes, expire after 12 hours, and are revoked on logout. Every protected request reloads active user and permission state from PostgreSQL.
- Owner bootstrap is a one-time CLI action after migration. It takes a transaction advisory lock and refuses to create another owner once any user exists.
- Vendor and item records have separate tables. Shared catalog terms enforce unique canonical names and aliases within each catalog. The Android picker may filter cached results instantly, but only the server can create or resolve a term.
- Bill arithmetic lives in Python and Kotlin domain code. The backend validates source price inputs and recomputes totals; each stored line retains whether rate or amount was entered. See `docs/bill-domain.md`.
- Database migrations are additive and reviewed; saved records are not silently reshaped.
- Photos are private objects. The database stores object keys and metadata, never long-lived public links.
- A signed PUT writes a temporary key. After size, type, and signature checks, the server copies it to a final private key and checks the copy before marking it ready. Signed GET URLs are issued only after API authorization.

## Keep v1 small
Use one Android app, one modular backend, and one PostgreSQL database. Do not introduce microservices, message brokers, or offline write synchronization for v1.
