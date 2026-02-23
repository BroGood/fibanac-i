from datetime import datetime

from fastapi.testclient import TestClient

from glow_crm.db import Base, engine
from glow_crm.main import app


client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def token_headers(tenant_id: int, role: str) -> dict[str, str]:
    resp = client.post("/auth/token", json={"tenant_id": tenant_id, "role": role})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_full_booking_and_gdpr_flow():
    tenant = client.post("/tenants", json={"name": "Glow Prague", "timezone": "Europe/Prague", "currency": "CZK"})
    assert tenant.status_code == 201
    tenant_id = tenant.json()["id"]

    admin = token_headers(tenant_id, "admin")

    service = client.post(
        f"/tenants/{tenant_id}/services",
        json={"name": "Haircut", "duration_min": 60, "buffer_min": 10, "price": 45.0},
        headers=admin,
    )
    assert service.status_code == 201
    service_id = service.json()["id"]

    staff = client.post(
        f"/tenants/{tenant_id}/staff",
        json={"full_name": "Pavel Novak", "service_ids": [service_id]},
        headers=admin,
    )
    assert staff.status_code == 201
    staff_id = staff.json()["id"]

    staff_token = token_headers(tenant_id, "staff")

    customer = client.post(
        f"/tenants/{tenant_id}/clients",
        json={"full_name": "Anna", "phone": "+420777111222", "email": "anna@example.com"},
        headers=staff_token,
    )
    assert customer.status_code == 201
    client_id = customer.json()["id"]

    booking = client.post(
        f"/tenants/{tenant_id}/appointments",
        json={
            "service_id": service_id,
            "staff_id": staff_id,
            "client_id": client_id,
            "starts_at": datetime(2026, 1, 10, 10, 0, 0).isoformat(),
        },
        headers=staff_token,
    )
    assert booking.status_code == 201

    consent = client.post(
        f"/tenants/{tenant_id}/clients/{client_id}/consents",
        json={"policy_version": "v1.0", "marketing_opt_in": True},
        headers=staff_token,
    )
    assert consent.status_code == 201

    export = client.get(f"/tenants/{tenant_id}/clients/{client_id}/gdpr-export", headers=admin)
    assert export.status_code == 200
    body = export.json()
    assert body["client"]["full_name"] == "Anna"
    assert len(body["appointments"]) == 1
    assert len(body["consents"]) == 1

    forget = client.delete(f"/tenants/{tenant_id}/clients/{client_id}", headers=admin)
    assert forget.status_code == 200
    assert forget.json()["is_anonymized"] is True


def test_prevents_staff_booking_overlap_and_cross_tenant_forbidden():
    tenant_1 = client.post("/tenants", json={"name": "Glow 1", "timezone": "Europe/Prague", "currency": "EUR"}).json()["id"]
    tenant_2 = client.post("/tenants", json={"name": "Glow 2", "timezone": "Europe/Prague", "currency": "EUR"}).json()["id"]

    admin_t1 = token_headers(tenant_1, "admin")
    admin_t2 = token_headers(tenant_2, "admin")

    service_id = client.post(
        f"/tenants/{tenant_1}/services",
        json={"name": "Nails", "duration_min": 60, "buffer_min": 15, "price": 30},
        headers=admin_t1,
    ).json()["id"]

    forbidden_cross_tenant = client.post(
        f"/tenants/{tenant_1}/services",
        json={"name": "Not allowed", "duration_min": 20, "buffer_min": 0, "price": 12},
        headers=admin_t2,
    )
    assert forbidden_cross_tenant.status_code == 403

    staff_id = client.post(
        f"/tenants/{tenant_1}/staff",
        json={"full_name": "Olga", "service_ids": [service_id]},
        headers=admin_t1,
    ).json()["id"]

    staff_t1 = token_headers(tenant_1, "staff")
    client_a = client.post(
        f"/tenants/{tenant_1}/clients",
        json={"full_name": "Anna A", "phone": "11111", "email": None},
        headers=staff_t1,
    ).json()["id"]
    client_b = client.post(
        f"/tenants/{tenant_1}/clients",
        json={"full_name": "Bella B", "phone": "22222", "email": None},
        headers=staff_t1,
    ).json()["id"]

    ok = client.post(
        f"/tenants/{tenant_1}/appointments",
        json={
            "service_id": service_id,
            "staff_id": staff_id,
            "client_id": client_a,
            "starts_at": datetime(2026, 1, 10, 11, 0, 0).isoformat(),
        },
        headers=staff_t1,
    )
    assert ok.status_code == 201

    clash = client.post(
        f"/tenants/{tenant_1}/appointments",
        json={
            "service_id": service_id,
            "staff_id": staff_id,
            "client_id": client_b,
            "starts_at": datetime(2026, 1, 10, 11, 30, 0).isoformat(),
        },
        headers=staff_t1,
    )
    assert clash.status_code == 409
    assert "conflict" in clash.json()["detail"].lower()
