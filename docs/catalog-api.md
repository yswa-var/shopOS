# Catalog API contract

Q02 adds two independent catalogs. Vendor and item IDs are UUIDs; later bill requests should store these IDs, not entered names. PostgreSQL remains authoritative.

| Operation | Vendor path | Item path | Permission |
|---|---|---|---|
| Search | `GET /catalog/vendors?q=` | `GET /catalog/items?q=` | `catalog:read` |
| Create | `POST /catalog/vendors` | `POST /catalog/items` | `catalog:write` |
| Add alias | `POST /catalog/vendors/{id}/aliases` | `POST /catalog/items/{id}/aliases` | `catalog:write` |

All routes require a bearer token. Owners can use every route. Employees need the listed grant; Q07 will provide account and grant management. Creation accepts `{"name":"Green Farms","aliases":["GF"]}`. Adding an alias accepts `{"alias":"Green Farm"}`. Responses contain `id`, canonical `name`, and `aliases`.

Names and aliases are trimmed, internal whitespace is collapsed, and comparison is case insensitive. A term is unique within its catalog, whether it is a canonical name or an alias. A collision returns HTTP 409 with `detail.existing_id` so a caller can search for and select the existing record. Duplicate terms inside one creation request return 422. Alias creation for an unknown record returns 404.

Search matches canonical names and aliases, returns at most 20 records, and ranks exact and prefix matches first. Within that rank, higher `use_count`, newer `last_used_at`, and newer creation come first. Q05 will update usage fields when bills are saved. The Android selector keeps recent search results in memory for immediate filtering, then replaces them with the server response; it does not write catalog data offline.
