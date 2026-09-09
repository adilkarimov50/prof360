"""Шифрование чувствительных полей и детерминированный хеш ИИН.

- Чувствительные значения (ИИН, адрес, телефон) шифруются Fernet перед записью в БД.
- Для поиска/дедупликации по ИИН хранится отдельный HMAC-SHA256 хеш (с перцем).
"""
import base64
import hashlib
import hmac

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    key = settings.field_encryption_key.encode()
    return Fernet(key)


def encrypt(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if token is None or token == "":
        return token
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return None


def iin_hash(iin: str | None) -> str | None:
    """Детерминированный хеш ИИН для индексирования и дедупликации."""
    if not iin:
        return None
    digest = hmac.new(settings.iin_hash_pepper.encode(), iin.encode(), hashlib.sha256)
    return base64.urlsafe_b64encode(digest.digest()).decode()


def mask_iin(iin: str | None) -> str:
    """Маскирование ИИН для отображения без полного доступа: 12 цифр -> ******7890."""
    if not iin:
        return ""
    if len(iin) <= 4:
        return "*" * len(iin)
    return "*" * (len(iin) - 4) + iin[-4:]
