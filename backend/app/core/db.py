"""Подключение к БД и базовый класс моделей."""
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Создаёт расширение pgvector и все таблицы (bootstrap для MVP)."""
    import app.models  # noqa: F401  регистрация моделей

    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception:
            conn.rollback()
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Добавляет новые колонки в существующие таблицы без Alembic."""
    alters = [
        "ALTER TABLE admin_cases ADD COLUMN IF NOT EXISTS legal_norm_id INTEGER",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
        "ALTER TABLE commission_documents ADD COLUMN IF NOT EXISTS analysis_legal JSON",
        "ALTER TABLE commission_documents ADD COLUMN IF NOT EXISTS legal_compliance_score FLOAT",
        # commission sessions module — created by create_all, kept here as safety
        "ALTER TABLE commission_sessions ADD COLUMN IF NOT EXISTS effectiveness_score FLOAT",
        "ALTER TABLE commission_executions ADD COLUMN IF NOT EXISTS quality_score FLOAT",
    ]
    with engine.connect() as conn:
        for stmt in alters:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()
