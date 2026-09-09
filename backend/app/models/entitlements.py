"""Справочники: коды МКБ-10 и меры государственной поддержки (соцвыплаты, пособия)."""
from datetime import datetime

from sqlalchemy import String, Integer, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class IcdCode(Base):
    __tablename__ = "icd_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(512))
    chapter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prevention_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    links: Mapped[list["EntitlementIcdLink"]] = relationship(back_populates="icd")


class Entitlement(Base):
    """Мера государственной поддержки с привязкой к норме на adilet."""

    __tablename__ = "entitlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    category: Mapped[str] = mapped_column(String(128), index=True)
    beneficiary: Mapped[str] = mapped_column(String(512))
    condition_text: Mapped[str] = mapped_column(Text)
    amount_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    administering_body: Mapped[str] = mapped_column(String(255))
    legal_act: Mapped[str] = mapped_column(String(512))
    legal_article: Mapped[str] = mapped_column(String(64))
    adilet_doc_id: Mapped[str] = mapped_column(String(32))
    adilet_url: Mapped[str] = mapped_column(String(512))
    prevention_relevance: Mapped[str | None] = mapped_column(Text, nullable=True)

    icd_links: Mapped[list["EntitlementIcdLink"]] = relationship(
        back_populates="entitlement", cascade="all, delete-orphan"
    )


class EntitlementIcdLink(Base):
    __tablename__ = "entitlement_icd_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    entitlement_id: Mapped[int] = mapped_column(ForeignKey("entitlements.id", ondelete="CASCADE"), index=True)
    icd_code: Mapped[str] = mapped_column(ForeignKey("icd_codes.code", ondelete="CASCADE"), index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    entitlement: Mapped["Entitlement"] = relationship(back_populates="icd_links")
    icd: Mapped["IcdCode"] = relationship(back_populates="links")


class PersonIcdCode(Base):
    """Код МКБ, привязанный к лицу (наркология, психиатрия, ручной ввод)."""

    __tablename__ = "person_icd_codes"
    __table_args__ = (
        UniqueConstraint("person_id", "icd_code", "source", name="uq_person_icd_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), index=True)
    icd_code: Mapped[str] = mapped_column(ForeignKey("icd_codes.code", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")  # narco | psych | manual
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    icd: Mapped["IcdCode"] = relationship()
