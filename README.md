# Glow CRM MVP (Backend v0.2)

Practical MVP backend for Glow CRM with:
- persistent SQL database (SQLite by default, can switch via `DATABASE_URL`),
- JWT auth and RBAC,
- tenant-scoped booking engine,
- GDPR flows (consent, export, anonymize),
- audit logging for sensitive actions.

## Implemented
- Multi-tenant entities: tenants, services, staff, clients.
- Appointment booking with service duration + buffer and overlap prevention.
- Tenant isolation checks (cross-tenant access denied).
- JWT token endpoint and role checks (`owner`, `admin`, `staff`, `client`).
- GDPR endpoints:
  - consent logging,
  - client data export,
  - client anonymization.

## Stack
- Python 3.10+
- FastAPI
- SQLAlchemy 2
- Pydantic v2
- PyJWT

## Run
```bash
pip install -r requirements.txt
uvicorn glow_crm.main:app --reload
```

## Quick auth usage
1. Create tenant:
```bash
curl -X POST http://127.0.0.1:8000/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Glow Prague","timezone":"Europe/Prague","currency":"CZK"}'
```
2. Get token for tenant role:
```bash
curl -X POST http://127.0.0.1:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"tenant_id":1,"role":"admin"}'
```
3. Use `Authorization: Bearer <token>` in protected endpoints.

## Test
```bash
pytest -q
```

## API docs
- Swagger UI: `http://127.0.0.1:8000/docs`
