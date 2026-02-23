from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    timezone: str = Field(default="Europe/Prague")
    currency: str = Field(default="EUR")


class TenantOut(BaseModel):
    id: int
    name: str
    timezone: str
    currency: str


class ServiceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    duration_min: int = Field(ge=10, le=480)
    buffer_min: int = Field(default=0, ge=0, le=120)
    price: float = Field(ge=0)


class ServiceOut(BaseModel):
    id: int
    tenant_id: int
    name: str
    duration_min: int
    buffer_min: int
    price: float


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    service_ids: List[int] = Field(default_factory=list)


class StaffOut(BaseModel):
    id: int
    tenant_id: int
    full_name: str
    service_ids: List[int]


class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=5, max_length=30)
    email: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    tenant_id: int
    full_name: str
    phone: str
    email: Optional[str]
    is_anonymized: bool


class AppointmentCreate(BaseModel):
    service_id: int
    staff_id: int
    client_id: int
    starts_at: datetime


class AppointmentOut(BaseModel):
    id: int
    tenant_id: int
    service_id: int
    staff_id: int
    client_id: int
    starts_at: datetime
    ends_at: datetime
    status: str


class ConsentCreate(BaseModel):
    policy_version: str = Field(min_length=1, max_length=30)
    marketing_opt_in: bool = False


class ConsentOut(BaseModel):
    id: int
    tenant_id: int
    client_id: int
    policy_version: str
    marketing_opt_in: bool
    created_at: datetime


class GDPRExportOut(BaseModel):
    client: ClientOut
    appointments: List[AppointmentOut]
    consents: List[ConsentOut]
