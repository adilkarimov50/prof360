"""Конфигурация приложения «Профилактика 360».

Все значения берутся из переменных окружения (.env). Секреты не хранятся в коде.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Общие ---
    app_name: str = "Профилактика 360"
    environment: str = "development"
    api_prefix: str = "/api"

    # --- База данных ---
    database_url: str = "postgresql+psycopg2://prof360:prof360@localhost:5432/prof360"

    # --- Безопасность ---
    jwt_secret: str = "change-me-in-production-please-use-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 7
    # Ключ Fernet для шифрования чувствительных полей (ИИН, адрес, телефон)
    field_encryption_key: str = "_Qk1lPrvsKtTzxT2ZwUFveJb_ItPyMofdiCQI-Lz0MA="
    # Перец для детерминированного HMAC-хеша ИИН (поиск/дедупликация)
    iin_hash_pepper: str = "prof360-iin-pepper-change-me"
    # Блокировка по неуспешным входам
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    # Порог массовой выгрузки (DLP)
    mass_export_threshold: int = 200

    # --- ИИ-консультант ---
    # Провайдер генерации: "ollama" (локально) или "gemini" (внешний API).
    ai_provider: str = "gemini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_enabled: bool = True
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dim: int = 384
    # Google Gemini (ключ задаётся через .env, в код не коммитится)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    # Разрешить отправку во внешний ИИ. ПДн всё равно токенизируются перед отправкой.
    ai_allow_external: bool = True
    # Максимум токенов в ответе генерации (развёрнутые ответы/акты/справки)
    ai_max_output_tokens: int = 3072

    # --- Данные для ETL (исходные Excel в корне проекта) ---
    data_dir: str = ".."

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """Refuse insecure defaults in production."""
        if self.environment != "production":
            return
        insecure = []
        if "change-me" in self.jwt_secret.lower():
            insecure.append("jwt_secret")
        if "change-me" in self.iin_hash_pepper.lower():
            insecure.append("iin_hash_pepper")
        if self.field_encryption_key.startswith("_Qk1"):
            insecure.append("field_encryption_key")
        if insecure:
            raise RuntimeError(f"Insecure defaults in production: {', '.join(insecure)}")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_production()
    return s


settings = get_settings()
