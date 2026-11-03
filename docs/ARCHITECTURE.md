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
- Database migrations are additive and reviewed; saved records are not silently reshaped.
- Photos are private objects. The database stores object keys and metadata, never long-lived public links.

## Keep v1 small
Use one Android app, one modular backend, and one PostgreSQL database. Do not introduce microservices, message brokers, or offline write synchronization for v1.
