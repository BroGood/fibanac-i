from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from glow_crm.repository import Appointment, AuditLog, Client, Consent, Service, Staff, StaffService, Tenant


def _require_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _ensure_tenant_scope(entity, tenant_id: int, name: str) -> None:
    if not entity or entity.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{name} not found")


def _audit(db: Session, tenant_id: int, role: str, action: str, details: str) -> None:
    db.add(AuditLog(tenant_id=tenant_id, actor_role=role, action=action, details=details))


def create_tenant(db: Session, name: str, timezone: str, currency: str, role: str = "owner") -> Tenant:
    tenant = Tenant(name=name, timezone=timezone, currency=currency)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    _audit(db, tenant.id, role, "tenant_created", f"name={name}")
    db.commit()
    return tenant


def create_service(db: Session, tenant_id: int, name: str, duration_min: int, buffer_min: int, price: float, role: str) -> Service:
    _require_tenant(db, tenant_id)
    row = Service(tenant_id=tenant_id, name=name, duration_min=duration_min, buffer_min=buffer_min, price=price)
    db.add(row)
    _audit(db, tenant_id, role, "service_created", f"service={name}")
    db.commit()
    db.refresh(row)
    return row


def create_staff(db: Session, tenant_id: int, full_name: str, service_ids: list[int], role: str) -> Staff:
    _require_tenant(db, tenant_id)

    for service_id in service_ids:
        service = db.get(Service, service_id)
        _ensure_tenant_scope(service, tenant_id, "Service")

    staff = Staff(tenant_id=tenant_id, full_name=full_name)
    db.add(staff)
    db.flush()

    for service_id in service_ids:
        db.add(StaffService(tenant_id=tenant_id, staff_id=staff.id, service_id=service_id))

    _audit(db, tenant_id, role, "staff_created", f"staff={full_name}")
    db.commit()
    db.refresh(staff)
    return staff


def get_staff_service_ids(db: Session, tenant_id: int, staff_id: int) -> list[int]:
    rows = db.scalars(
        select(StaffService.service_id).where(
            and_(StaffService.tenant_id == tenant_id, StaffService.staff_id == staff_id)
        )
    ).all()
    return list(rows)


def create_client(db: Session, tenant_id: int, full_name: str, phone: str, email: str | None, role: str) -> Client:
    _require_tenant(db, tenant_id)
    row = Client(tenant_id=tenant_id, full_name=full_name, phone=phone, email=email)
    db.add(row)
    _audit(db, tenant_id, role, "client_created", f"client={full_name}")
    db.commit()
    db.refresh(row)
    return row


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def create_appointment(db: Session, tenant_id: int, service_id: int, staff_id: int, client_id: int, starts_at, role: str) -> Appointment:
    _require_tenant(db, tenant_id)

    service = db.get(Service, service_id)
    staff = db.get(Staff, staff_id)
    client = db.get(Client, client_id)

    _ensure_tenant_scope(service, tenant_id, "Service")
    _ensure_tenant_scope(staff, tenant_id, "Staff")
    _ensure_tenant_scope(client, tenant_id, "Client")

    service_ids = set(get_staff_service_ids(db, tenant_id, staff_id))
    if service_id not in service_ids:
        raise HTTPException(status_code=400, detail="Staff is not qualified for the selected service")

    ends_at = starts_at + timedelta(minutes=service.duration_min + service.buffer_min)
    existing = db.scalars(
        select(Appointment).where(
            and_(
                Appointment.tenant_id == tenant_id,
                Appointment.staff_id == staff_id,
            )
        )
    ).all()

    for row in existing:
        if _overlaps(starts_at, ends_at, row.starts_at, row.ends_at):
            raise HTTPException(status_code=409, detail="Booking conflict for staff schedule")

    appt = Appointment(
        tenant_id=tenant_id,
        service_id=service_id,
        staff_id=staff_id,
        client_id=client_id,
        starts_at=starts_at,
        ends_at=ends_at,
        status="booked",
    )
    db.add(appt)
    _audit(db, tenant_id, role, "appointment_created", f"staff_id={staff_id};client_id={client_id}")
    db.commit()
    db.refresh(appt)
    return appt


def list_day_appointments(db: Session, tenant_id: int, booking_date: date) -> list[Appointment]:
    _require_tenant(db, tenant_id)
    rows = db.scalars(select(Appointment).where(Appointment.tenant_id == tenant_id)).all()
    return [row for row in rows if row.starts_at.date() == booking_date]


def create_consent(db: Session, tenant_id: int, client_id: int, policy_version: str, marketing_opt_in: bool, role: str) -> Consent:
    _require_tenant(db, tenant_id)
    client = db.get(Client, client_id)
    _ensure_tenant_scope(client, tenant_id, "Client")

    row = Consent(
        tenant_id=tenant_id,
        client_id=client_id,
        policy_version=policy_version,
        marketing_opt_in=marketing_opt_in,
    )
    db.add(row)
    _audit(db, tenant_id, role, "consent_logged", f"client_id={client_id};policy={policy_version}")
    db.commit()
    db.refresh(row)
    return row


def export_client_data(db: Session, tenant_id: int, client_id: int):
    _require_tenant(db, tenant_id)
    client = db.get(Client, client_id)
    _ensure_tenant_scope(client, tenant_id, "Client")

    appointments = db.scalars(
        select(Appointment).where(and_(Appointment.tenant_id == tenant_id, Appointment.client_id == client_id))
    ).all()
    consents = db.scalars(select(Consent).where(and_(Consent.tenant_id == tenant_id, Consent.client_id == client_id))).all()

    return client, appointments, consents


def anonymize_client(db: Session, tenant_id: int, client_id: int, role: str) -> Client:
    _require_tenant(db, tenant_id)
    client = db.get(Client, client_id)
    _ensure_tenant_scope(client, tenant_id, "Client")

    client.full_name = f"anonymized-{client.id}"
    client.phone = "anonymized"
    client.email = None
    client.is_anonymized = True
    _audit(db, tenant_id, role, "client_anonymized", f"client_id={client_id}")
    db.commit()
    db.refresh(client)
    return client
