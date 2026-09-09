"""Pydantic auth schemas."""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    requires_totp_setup: bool = False
    requires_password_change: bool = False


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    district: str | None = None
    can_export: bool
    can_access_minors: bool
    totp_enabled: bool
    must_change_password: bool = False

    class Config:
        from_attributes = True
