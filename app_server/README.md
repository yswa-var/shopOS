# ShopOS API starter

Copy `.env.example` to `.env` and set the PostgreSQL credentials. The configured
user must be able to connect to `DB_ADMIN_DATABASE` and create `DB_NAME` when it
does not exist.

Start the FastAPI development server with:

```bash
uv run uvicorn main:app --reload
```

Available starter endpoints:

- `GET /` — basic API response
- `GET /health` — verifies the PostgreSQL connection
- `GET /docs` — interactive OpenAPI documentation

On API startup, `DatabaseBootstrap`:

1. creates `DB_NAME` when needed;
2. verifies the six purchase-bill tables;
3. applies `dbops/001_create_purchase_bills.sql` only to an empty schema; and
4. stops with an error if it finds a partial schema, leaving existing data alone.

Use the injected `DatabaseDependency` in new endpoints. Database operations are
available through `fetch_one`, `fetch_all`, and atomic `execute` methods:

```python
@app.get("/api/vendors")
async def vendors(database: DatabaseDependency):
    return await database.fetch_all("SELECT * FROM vendors ORDER BY id")
```

## User access

Startup creates an `api_users` table. Catalog and bill endpoints require an
individual username and password over HTTPS. Create and disable accounts with:

```bash
uv run python manage_users.py add alice
uv run python manage_users.py disable alice
```

The add command prompts for a password and stores only its Argon2 hash. To
manage users in Render PostgreSQL from your Mac, configure the external database
host in your local `.env`. The Render API service uses the internal host.
`/health` remains public.


