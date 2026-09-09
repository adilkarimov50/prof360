"""Аутентификация: вход (пароль + 2FA), refresh, настройка TOTP, профиль."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import client_ip, get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)
from app.models.user import User
from app.schemas import LoginRequest, TokenResponse, TotpSetupResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class RefreshRequest(BaseModel):
    refresh_token: str


class TotpEnableRequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


def _token_response(user: User) -> TokenResponse:
    tv = user.token_version
    return TokenResponse(
        access_token=create_access_token(user.username, user.role.value, tv),
        refresh_token=create_refresh_token(user.username, tv),
        role=user.role.value,
        full_name=user.full_name,
        requires_totp_setup=not user.totp_enabled,
        requires_password_change=user.must_change_password,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    ip = client_ip(request)

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")

    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
        log_action(db, action="login_locked", user=user, ip=ip)
        raise HTTPException(status_code=status.HTTP_423_LOCKED,
                            detail="Учётная запись временно заблокирована")

    if not verify_password(data.password, user.hashed_password):
        user.failed_attempts += 1
        if user.failed_attempts >= settings.max_login_attempts:
            user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=settings.lockout_minutes)
            user.failed_attempts = 0
        db.commit()
        log_action(db, action="login_failed", user=user, ip=ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные учётные данные")

    if user.totp_enabled:
        if not data.totp_code:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется код 2FA")
        if not verify_totp(user.totp_secret, data.totp_code):
            log_action(db, action="login_2fa_failed", user=user, ip=ip)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный код 2FA")

    user.failed_attempts = 0
    user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    log_action(db, action="login_success", user=user, ip=ip)

    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh-токен")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь недоступен")
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия завершена")
    return _token_response(user)


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    log_action(db, action="logout", user=user, ip=client_ip(request))
    return {"status": "ok"}


@router.post("/change-password")
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный текущий пароль")
    user.hashed_password = hash_password(data.new_password)
    user.must_change_password = False
    user.token_version += 1
    db.commit()
    log_action(db, action="password_changed", user=user, ip=client_ip(request))
    return _token_response(user)


@router.post("/2fa/setup", response_model=TotpSetupResponse)
def setup_totp(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    secret = generate_totp_secret()
    user.totp_secret = secret
    db.commit()
    return TotpSetupResponse(secret=secret, provisioning_uri=totp_provisioning_uri(secret, user.username))


@router.post("/2fa/enable")
def enable_totp(data: TotpEnableRequest, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.totp_secret or not verify_totp(user.totp_secret, data.code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный код подтверждения 2FA")
    user.totp_enabled = True
    db.commit()
    log_action(db, action="2fa_enabled", user=user, ip=client_ip(request))
    return {"status": "ok", "totp_enabled": True}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
