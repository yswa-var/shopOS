# Owner employee management

Only the owner can call `/employees` endpoints. The owner screen is hidden from employees, and the server's owner check remains authoritative even if an employee is manually given an `employees:manage` permission string. The owner account itself cannot be changed through these employee endpoints.

| Endpoint | Purpose |
|---|---|
| `GET /employees/permissions` | Available grant keys, labels, and new-employee defaults |
| `GET /employees` | Active and inactive employee list with current grants |
| `POST /employees` | Create an employee with username, display name, initial password, and grants |
| `PUT /employees/{id}/permissions` | Replace grants with an explicit list |
| `PUT /employees/{id}/profile` | Change display name |
| `PUT /employees/{id}/password` | Reset password and revoke existing sessions |
| `PUT /employees/{id}/status` | Deactivate or reactivate; deactivation revokes sessions |

Usernames are normalized to lowercase and must match the Q01 username policy; duplicate names return 409. Passwords are 12–256 characters and are never returned by the API or stored in Android drafts. Permission keys are restricted to the server catalog, and duplicate or unknown grants return 422. New employees receive the six grants needed to create and find bills by default; the owner can narrow them before creating an account or change them later. Grant changes take effect on the next protected request because the API reloads the user from PostgreSQL. Reactivation does not revive old sessions; the employee must sign in again.

All state changes and their audit events commit in the same transaction. Repeating an unchanged status, profile, or permission update does not add an audit event. Q07 uses the existing user, permission, session, and audit tables; no migration is needed.
