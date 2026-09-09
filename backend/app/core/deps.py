"""Зависимости FastAPI: текущий пользователь, проверки RBAC/ABAC."""
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_token
from app.models.user import User, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизовано")
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь недоступен")
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия завершена")
    return user


def require_roles(*roles: Role) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав (RBAC)")
        return user

    return checker


def require_export(user: User = Depends(get_current_user)) -> User:
    """DLP: экспорт только при наличии права."""
    if not user.can_export:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет права на экспорт")
    return user


def require_minors_access(user: User = Depends(get_current_user)) -> User:
    if not user.can_access_minors:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет спец-доступа к данным несовершеннолетних")
    return user


def abac_district_filter(user: User) -> str | None:
    """ABAC: районный прокурор видит только свой район; область/аналитики — всё."""
    territorial = {Role.DISTRICT_PROSECUTOR}
    if user.role in territorial and user.district:
        return user.district
    return None


def client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None
