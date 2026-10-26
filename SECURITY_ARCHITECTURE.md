# Backend architecture and security notes

## Current structure

- `api/` defines HTTP routes and delegates work to `services/`.
- `services/` holds workflows and database operations; `models/` contains table/query code.
- `schemas/` validates request data and shapes responses.
- `security/` contains bearer-token and role dependencies; `utils/jwt.py` owns token encoding and verification.
- `database.py` is the single engine, session factory, schema bootstrap, and request session dependency.
- `exceptions/handlers.py` formats HTTP, validation, integrity, database, and unexpected errors.
- `middleware/request_id.py` assigns a server-generated correlation ID to each request.
- `tests/` contains unittest-based service and API checks.

## Endpoint workflow

Add a Pydantic schema, route in `api/`, and business/database operation in `services/` with model queries in `models/`. Inject `get_db` from `database.py`. Require an explicit security dependency on each protected route: `require_admin` for administration, `require_staff` for assigned-teacher workflows, or `require_admin_or_staff` for staff/admin reads. Resource ownership and class assignment checks must remain in the service query path; authentication alone is not resource authorization.

## Errors and request IDs

Raise `HTTPException` for expected HTTP failures. Global handlers return the shape below and attach the same server-generated ID in the `X-Request-ID` header. Unexpected failures are logged server-side and return a generic message. Validation responses intentionally omit submitted values and Pydantic context to avoid echoing passwords or personal information.

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    "request_id": "server-generated-uuid"
  }
}
```

## Configuration and operations

Set `DATABASE_URL` and `JWT_SECRET_KEY` through the deployment secret store. Use a unique, high-entropy JWT key per environment; rotate any credential found in a tracked file or Git history. `JWT_ALGORITHM`, token lifetimes, `ENVIRONMENT`, `JWT_COOKIE_SECURE`, and `JWT_COOKIE_SAMESITE` control token and cookie behavior. Keep `.env` out of version control. CORS origins are currently maintained in `server.py` and should be aligned with each deployment's frontend origin.

Install the declared requirements, run `python -m unittest discover -s tests`, and use the repository's configured dependency scanner when available. The current schema bootstrap executes DDL during application startup; production schema changes should be reviewed and applied through a controlled migration process before deploying code that depends on them. Do not run bootstrap or schema tests against production.

## Reviewed routes and remaining authorization work

All registered routes in `api/` were enumerated. Grade, section, subject, timetable, and school-wide attendance reads require admin/staff access; Student attendance-list requests are scoped to the student's own ID. Students use `/api/scheduling/student/sessions` and `/api/attendance/me`, which derive the record identity and class from the active authenticated student account. Staff can update only the conducted status and remarks of class sessions assigned to their active staff profile. Session creation, reassignment, and deletion remain admin-only. Authentication/session routes remain public where necessary (`login`, refresh-cookie rotation, and logout); `/health` remains public. Other route groups already declared role dependencies. This project has no evident school/tenant key, so tenant isolation could not be verified or implemented from available data structures.

The API error format changed to a consistent `error` object; clients that parse FastAPI's previous `detail` field should be updated. Protected routes now require bearer authorization where they were previously public. No database migration was added.
