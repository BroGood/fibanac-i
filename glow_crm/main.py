from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from glow_crm import service
from glow_crm.auth import AuthContext, TokenRequest, TokenResponse, issue_token, require_roles
from glow_crm.db import Base, engine, get_db
from glow_crm.schemas import (
    AppointmentCreate,
    AppointmentOut,
    ClientCreate,
    ClientOut,
    ConsentCreate,
    ConsentOut,
    GDPRExportOut,
    ServiceCreate,
    ServiceOut,
    StaffCreate,
    StaffOut,
    TenantCreate,
    TenantOut,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Glow CRM MVP API", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/token", response_model=TokenResponse)
def generate_token(payload: TokenRequest):
    token = issue_token(payload.tenant_id, payload.role)
    return TokenResponse(access_token=token)


@app.post("/tenants", response_model=TenantOut, status_code=201)
def create_tenant(payload: TenantCreate, db: Session = Depends(get_db)):
    return service.create_tenant(db, payload.name, payload.timezone, payload.currency, role="owner")


def _guard_tenant(ctx: AuthContext, tenant_id: int) -> None:
    if ctx.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")


@app.post("/tenants/{tenant_id}/services", response_model=ServiceOut, status_code=201)
def create_service(
    tenant_id: int,
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin")),
):
    _guard_tenant(ctx, tenant_id)
    return service.create_service(db, tenant_id, payload.name, payload.duration_min, payload.buffer_min, payload.price, ctx.role)


@app.post("/tenants/{tenant_id}/staff", response_model=StaffOut, status_code=201)
def create_staff(
    tenant_id: int,
    payload: StaffCreate,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin")),
):
    _guard_tenant(ctx, tenant_id)
    staff = service.create_staff(db, tenant_id, payload.full_name, payload.service_ids, ctx.role)
    service_ids = service.get_staff_service_ids(db, tenant_id, staff.id)
    return {"id": staff.id, "tenant_id": staff.tenant_id, "full_name": staff.full_name, "service_ids": service_ids}


@app.post("/tenants/{tenant_id}/clients", response_model=ClientOut, status_code=201)
def create_client(
    tenant_id: int,
    payload: ClientCreate,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin", "staff")),
):
    _guard_tenant(ctx, tenant_id)
    return service.create_client(db, tenant_id, payload.full_name, payload.phone, payload.email, ctx.role)


@app.post("/tenants/{tenant_id}/appointments", response_model=AppointmentOut, status_code=201)
def create_appointment(
    tenant_id: int,
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin", "staff")),
):
    _guard_tenant(ctx, tenant_id)
    return service.create_appointment(
        db,
        tenant_id=tenant_id,
        service_id=payload.service_id,
        staff_id=payload.staff_id,
        client_id=payload.client_id,
        starts_at=payload.starts_at,
        role=ctx.role,
    )


@app.get("/tenants/{tenant_id}/appointments/day", response_model=list[AppointmentOut])
def list_day_appointments(
    tenant_id: int,
    booking_date: date,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin", "staff")),
):
    _guard_tenant(ctx, tenant_id)
    return service.list_day_appointments(db, tenant_id, booking_date)


@app.post("/tenants/{tenant_id}/clients/{client_id}/consents", response_model=ConsentOut, status_code=201)
def create_consent(
    tenant_id: int,
    client_id: int,
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin", "staff")),
):
    _guard_tenant(ctx, tenant_id)
    return service.create_consent(db, tenant_id, client_id, payload.policy_version, payload.marketing_opt_in, ctx.role)


@app.get("/tenants/{tenant_id}/clients/{client_id}/gdpr-export", response_model=GDPRExportOut)
def gdpr_export(
    tenant_id: int,
    client_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin")),
):
    _guard_tenant(ctx, tenant_id)
    client, appointments, consents = service.export_client_data(db, tenant_id, client_id)
    return {"client": client, "appointments": appointments, "consents": consents}


@app.delete("/tenants/{tenant_id}/clients/{client_id}", response_model=ClientOut)
def gdpr_forget(
    tenant_id: int,
    client_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_roles("owner", "admin")),
):
    _guard_tenant(ctx, tenant_id)
    return service.anonymize_client(db, tenant_id, client_id, ctx.role)
