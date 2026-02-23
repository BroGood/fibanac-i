from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

JWT_SECRET = os.getenv("JWT_SECRET", "glow-dev-secret-change-me")
JWT_ALG = "HS256"
TOKEN_TTL_MIN = int(os.getenv("TOKEN_TTL_MIN", "720"))

security = HTTPBearer(auto_error=True)


class TokenRequest(BaseModel):
    tenant_id: int = Field(gt=0)
    role: str = Field(pattern="^(owner|admin|staff|client)$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthContext(BaseModel):
    tenant_id: int
    role: str


def issue_token(tenant_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=TOKEN_TTL_MIN)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def get_auth_context(credentials: HTTPAuthorizationCredentials = Depends(security)) -> AuthContext:
    token = credentials.credentials
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        tenant_id = int(data.get("tenant_id"))
        role = str(data.get("role"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if role not in {"owner", "admin", "staff", "client"}:
        raise HTTPException(status_code=401, detail="Invalid role in token")

    return AuthContext(tenant_id=tenant_id, role=role)


def require_roles(*roles: str):
    allowed = set(roles)

    def checker(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return ctx

    return checker
